# Guía de Testing - Chess Tactics Orchestrator

Cómo probar el sistema completo paso a paso.

---

## Pre-requisitos

### 1. Docker Desktop

Verifica que está corriendo:
```bash
docker ps
```

Si no:
```bash
# Mac: Abrir Docker Desktop app
# Linux: sudo systemctl start docker
```

### 2. Variables de Entorno

El archivo `.env` ya tiene las claves configuradas:
```bash
cat .env
# Verifica:
# GEMINI_API_KEY=AQ.Ab8RN...
# LICHESS_API_TOKEN=lip_hSksm...
# STOCKFISH_PATH=/opt/homebrew/bin/stockfish
```

### 3. Dependencias

```bash
export PATH="$HOME/.local/bin:$PATH"
uv sync
```

---

## Test 1: Services (Redis + Phoenix)

```bash
# Terminal 1
docker-compose up -d
```

**Verificar:**
```bash
docker ps
# Debe mostrar:
# - chess-tactics-redis (puerto 6379)
# - chess-tactics-phoenix (puerto 6006)

# Test Redis
docker exec chess-tactics-redis redis-cli ping
# Output: PONG

# Test Phoenix
curl http://localhost:6006
# Output: HTML de Phoenix UI
```

**Dashboard Phoenix:**
- Abrir: http://localhost:6006
- Debe mostrar interfaz vacía (sin traces todavía)

---

## Test 2: API

```bash
# Terminal 2
./run_api.sh
```

**Debe mostrar:**
```
Starting Chess Tactics Orchestrator API...
Docs: http://localhost:8000/docs
Health: http://localhost:8000/api/health

✓ Connected to Redis
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Verificar en Terminal 3:**
```bash
# Health check
curl http://localhost:8000/api/health
# Output:
# {"status":"healthy","redis_connected":true,"queue_length":0,...}

# Swagger docs
open http://localhost:8000/docs
# Debe abrir browser con FastAPI docs interactivos
```

---

## Test 3: Worker

```bash
# Terminal 4
./run_worker.sh
```

**Debe mostrar:**
```
Starting Chess Tactics Worker...
Polling queue: job_queue

🚀 Starting job worker...
  Polling queue: job_queue
  Press Ctrl+C to stop

✓ Worker initialized
```

El worker queda en modo polling (esperando jobs).

---

## Test 4: Job Simple (Sin HITL)

```bash
# Terminal 5
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "user_request": "¿cómo me va con la siciliana con negras?",
    "metadata": {"username": "isabido86"}
  }'
```

**Output esperado:**
```json
{
  "job_id": "abc123...",
  "status": "queued",
  "user_request": "¿cómo me va con la siciliana con negras?",
  ...
}
```

**Copiar el `job_id` y verificar en Terminal 4 (Worker):**
```
============================================================
📋 Processing job: abc123...
============================================================
  Request: ¿cómo me va con la siciliana con negras?
  ▶️  Starting new execution

  🔍 Parámetros de búsqueda:
    - username: isabido86
    - opening_filter: Sicilian
    - color: black
    - max_games: 200

  📋 Aperturas encontradas...

  ⏸️  Interrupted at HITL checkpoint
  Status: waiting_approval
```

**Ver status en Terminal 5:**
```bash
curl http://localhost:8000/api/jobs/abc123
```

```json
{
  "status": "waiting_approval",
  "result": {
    "games_analyzed": 20,
    "analysis_result": {...}
  }
}
```

---

## Test 5: HITL Approval

```bash
# Terminal 5 - Aprobar
curl -X POST http://localhost:8000/api/jobs/abc123/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "feedback": "OK"}'
```

**Ver en Terminal 4 (Worker):**
```
============================================================
📋 Processing job: abc123... (resumed)
============================================================
  🔄 Resuming from checkpoint
  ✓ Completed
  Status: completed
```

**Verificar resultado final:**
```bash
curl http://localhost:8000/api/jobs/abc123
```

```json
{
  "status": "completed",
  "result": {
    "final_answer": "Analizadas 94 partidas con Defensa Siciliana con negras...",
    "analysis_result": {
      "metrics": {
        "color_winrates": {"black": {"winrate": 0.606, "games": 94}},
        "total_blunders": 54
      }
    }
  }
}
```

---

## Test 6: Phoenix Traces

**Abrir:** http://localhost:6006

**Navegar:**
1. Click "Traces" tab (sidebar izquierdo)
2. Filtrar por proyecto: "chess-tactics-orchestrator"
3. Ver lista de traces (uno por job procesado)
4. Click en trace → ver spans jerárquicos:
   ```
   worker_process_job (45.3s)
   ├─ research_agent (12.1s)
   │  └─ Lichess API call
   └─ analyst_agent (33.2s)
      ├─ compute_metrics (18.4s)
      │  └─ Stockfish evaluations
      └─ interpret_metrics (14.8s)
          └─ Gemini LLM call
   ```

**Capturar screenshot:**
- Click en el trace del job `abc123`
- Screenshot completo mostrando spans + tiempos
- Guardar como: `phoenix_trace_screenshot.png`

---

## Test 7: Load Test (5 Concurrent)

```bash
# Terminal 5 (con API + Worker corriendo)
python load_test.py
```

**Debe mostrar:**
```
Load Test: 5 Concurrent Jobs
============================================================

[Job 1] Starting...
[Job 2] Starting...
[Job 3] Starting...
[Job 4] Starting...
[Job 5] Starting...

[Job 1] Created: job-1-uuid
[Job 2] Created: job-2-uuid
...

[Job 1] ⏸️  HITL reached (32.1s)
[Job 2] ⏸️  HITL reached (33.5s)
...

[Job 1] ✓ Approved
[Job 2] ✓ Approved
...

[Job 1] ✅ Completed (45.3s total)
[Job 2] ✅ Completed (47.1s total)
...

============================================================
Load Test Results
============================================================

Success: 5/5
Failed: 0/5

Latency (average):
  Total: 46.2s
  To HITL: 32.8s
  After approval: 13.4s

✓ Detailed results saved to: load_test_results.json
```

**Verificar archivo generado:**
```bash
cat load_test_results.json | jq '.[] | {job_num, success, total_latency}'
```

**Ver en Phoenix:**
- Refresh http://localhost:6006
- Debe mostrar 5 traces nuevos
- Comparar latencias entre jobs concurrentes

---

## Test 8: Rechazo HITL

```bash
# Crear job
JOB_ID=$(curl -s -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"user_request": "¿cómo me va con la siciliana últimos 3 juegos?"}' \
  | jq -r '.job_id')

# Esperar HITL
sleep 30

# Rechazar (pedir más partidas)
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": false, "feedback": "Need 10+ games"}'
```

**Worker debe refinar:**
```
  🔄 Resuming from checkpoint
  needs_refinement: True
  refine_target: research

  🔍 Re-fetching games with broader filters...

  ⏸️  Interrupted at HITL checkpoint (again)
```

**Aprobar segunda vez:**
```bash
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

---

## Troubleshooting

### Worker no procesa

**Verificar Redis:**
```bash
redis-cli LLEN job_queue
# Si >0: hay jobs pendientes pero worker no corre
```

**Reiniciar worker:**
```bash
# Ctrl+C en Terminal 4
./run_worker.sh
```

### API no responde

```bash
# Verificar puerto 8000 libre
lsof -i :8000

# Si ocupado, kill proceso
kill -9 <PID>

# Reiniciar
./run_api.sh
```

### Phoenix sin traces

```bash
# Verificar PHOENIX_ENABLED
grep PHOENIX_ENABLED run_worker.sh
# Debe ser: export PHOENIX_ENABLED=true

# Reiniciar worker
```

### Gemini quota exceeded

**Error en worker:**
```
❌ Failed: 429 RESOURCE_EXHAUSTED
```

**Solución:**
- Esperar cooldown (15-60 min)
- O usar otra API key

---

## Limpieza

```bash
# Parar servicios
docker-compose down

# Limpiar Redis data
docker-compose down -v

# Parar API/Worker
# Ctrl+C en cada terminal
```

---

## Checklist Final

- [ ] Services (Redis + Phoenix) corriendo
- [ ] API health check OK
- [ ] Worker polling queue
- [ ] Job creado y procesado hasta HITL
- [ ] HITL aprobado y completado
- [ ] Phoenix muestra traces con latencias
- [ ] Load test 5 concurrent jobs exitoso
- [ ] Screenshot de Phoenix trace capturado
- [ ] `load_test_results.json` generado

**Listo para presentar entregable.**
