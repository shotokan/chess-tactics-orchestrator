# Chess Tactics Orchestrator - API Documentation

Sistema multi-agente asíncrono para análisis de partidas de ajedrez con LLM + Stockfish.

## Arquitectura

```
Client → FastAPI → Redis Queue → Worker → LangGraph → Agents
                                    ↓
                            Phoenix (observability)
```

### Componentes

- **FastAPI**: API REST asíncrona (puerto 8000)
- **Worker**: Background processor con asyncio
- **Redis**: Job queue + checkpoints de LangGraph
- **Phoenix**: Observabilidad OpenTelemetry (puerto 6006)
- **LangGraph**: Multi-agent orchestration con HITL
- **Gemini**: LLM para interpretación (gemini-3.5-flash)
- **Stockfish**: Engine local para evaluación de posiciones

---

## Quick Start

### 1. Iniciar Services

```bash
docker-compose up -d
# Inicia: Redis (6379) + Phoenix (6006)
```

### 2. Iniciar API (Terminal 1)

```bash
./run_api.sh
# http://localhost:8000/docs
```

### 3. Iniciar Worker (Terminal 2)

```bash
./run_worker.sh
# Polling job_queue...
```

### 4. Crear Job

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "user_request": "¿cómo me va con la siciliana con negras?",
    "metadata": {"username": "isabido86", "priority": 5}
  }'
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "user_request": "¿cómo me va con la siciliana con negras?",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### 5. Poll Status

```bash
curl http://localhost:8000/api/jobs/{job_id}
```

**Estados posibles:**
- `queued`: En cola, esperando worker
- `processing`: Worker ejecutando análisis
- `waiting_approval`: Pausado en HITL checkpoint (ver resultado parcial)
- `completed`: Análisis completo
- `failed`: Error (ver campo `error`)

### 6. Aprobar HITL

Cuando `status == "waiting_approval"`:

```bash
curl -X POST http://localhost:8000/api/jobs/{job_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "feedback": "OK"}'
```

O rechazar para refinamiento:

```bash
curl -X POST http://localhost:8000/api/jobs/{job_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": false, "feedback": "Need 20+ games"}'
```

---

## API Endpoints

### Health Check

```
GET /api/health
```

Response:
```json
{
  "status": "healthy",
  "redis_connected": true,
  "queue_length": 3,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Create Job

```
POST /api/jobs
```

Body:
```json
{
  "user_request": "¿cómo me va con la Siciliana Dragón últimos 3 meses?",
  "metadata": {
    "username": "isabido86",
    "priority": 5,
    "tags": ["opening-analysis"]
  }
}
```

Response: `202 Accepted` + JobResponse

### Get Job Status

```
GET /api/jobs/{job_id}
```

Response:
```json
{
  "job_id": "uuid",
  "status": "waiting_approval",
  "user_request": "...",
  "created_at": "...",
  "updated_at": "...",
  "result": {
    "analysis_result": {
      "metrics": {
        "games_analyzed": 20,
        "color_winrates": {"black": {"winrate": 0.65, "games": 20}},
        "total_blunders": 12
      },
      "interpretation": "Analizadas 20 partidas..."
    },
    "games_analyzed": 20
  },
  "error": null
}
```

### Approve/Reject HITL

```
POST /api/jobs/{job_id}/approve
```

Body:
```json
{
  "approved": true,
  "feedback": "Results look good"
}
```

Response:
```json
{
  "job_id": "uuid",
  "status": "processing",
  "message": "Job approved - resuming to completion"
}
```

### Cancel Job

```
DELETE /api/jobs/{job_id}
```

Response: `204 No Content`

---

## Flujo HITL (Human-in-the-Loop)

```
1. POST /api/jobs → job_id, status=queued
2. Worker dequeue → status=processing
3. Graph: research → analyst → supervisor
4. Supervisor detecta: analysis_result sin aprobar
5. Graph interrupt antes de hitl_approval node
6. Worker: status=waiting_approval (checkpoint saved)
7. Client poll → ve analysis_result parcial
8. Client POST /approve con approved=true
9. Worker resume desde checkpoint
10. Graph: hitl_approval → supervisor → END
11. Worker: status=completed
12. Client poll → ve final_answer
```

**¿Por qué HITL?**
- Control de calidad antes de entregar al usuario
- Permite refinamiento si análisis insuficiente (ej. solo 5 partidas)
- Evita costos de LLM si resultado no útil

---

## Observabilidad con Phoenix

### Ver Traces

1. Abrir: http://localhost:6006
2. Filtrar proyecto: `chess-tactics-orchestrator`
3. Ver spans:
   - `worker_process_job` (latencia total)
   - `research_agent` (Lichess API calls)
   - `analyst_agent` → `compute_metrics` (Stockfish)
   - `analyst_agent` → `interpret_metrics` (LLM)

### Métricas Capturadas

- **Latencia por agente**
- **LLM tokens** (input/output) → estimación de costos
- **Stockfish evaluations** (count)
- **Redis operations** (queue, checkpoints)

### Estimación de Costos

Gemini 3.5 Flash pricing (aproximado):
- Input: $0.075 / 1M tokens
- Output: $0.30 / 1M tokens

Ver en Phoenix dashboard:
- Total tokens por job
- Tokens por agente (research vs analyst)

---

## Load Testing

### Ejecutar Test

```bash
python load_test.py
# 5 concurrent jobs
```

Output:
```
Success: 5/5
Latency (average):
  Total: 45.3s
  To HITL: 32.1s
  After approval: 13.2s

✓ Detailed results saved to: load_test_results.json
```

Ver traces en Phoenix: http://localhost:6006

---

## Variables de Entorno

```bash
# API Keys
GEMINI_API_KEY=your_key_here
LICHESS_API_TOKEN=lip_your_token  # Optional, higher rate limits

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Stockfish
STOCKFISH_PATH=/opt/homebrew/bin/stockfish  # Mac
# STOCKFISH_PATH=/usr/bin/stockfish  # Linux

# Phoenix
PHOENIX_ENABLED=true
PHOENIX_ENDPOINT=http://localhost:6006

# Checkpoints
CHECKPOINT_ENABLED=true
```

---

## Desarrollo

### Estructura

```
src/chess_tactics_orchestrator/
├── api/
│   ├── app.py              # FastAPI app
│   └── routes/
│       ├── health.py       # GET /health
│       └── jobs.py         # CRUD jobs + approval
├── infrastructure/
│   ├── redis_client.py     # Async Redis ops
│   └── checkpoint.py       # RedisSaver factory
├── observability/
│   └── phoenix_tracer.py   # OpenTelemetry setup
├── models/
│   └── job.py              # Pydantic models
├── agents/
│   ├── research_agent.py   # Lichess API
│   ├── analyst_agent.py    # Metrics + LLM
│   ├── supervisor.py       # Routing + validation
│   └── hitl_node.py        # HITL placeholder
├── tools/
│   ├── lichess_client.py   # Lichess API wrapper
│   ├── stockfish_eval.py   # Position evaluation
│   └── tactic_detector.py  # Blunder classification
├── graph.py                # LangGraph definition
├── state.py                # AgentState schema
└── worker.py               # Background processor
```

### Tests

```bash
# Unit tests
pytest tests/

# Integration test
python test_worker_integration.py

# Load test
python load_test.py
```

---

## Troubleshooting

### Worker no procesa jobs

```bash
# Check Redis connection
redis-cli ping

# Check queue
redis-cli LLEN job_queue

# Check worker logs
# Should see: "Polling queue: job_queue"
```

### Job stuck en "processing"

```bash
# Check worker is running
ps aux | grep worker

# Check job status in Redis
redis-cli HGETALL job:{job_id}

# Check for errors in worker logs
```

### Phoenix no muestra traces

```bash
# Check Phoenix is running
curl http://localhost:6006

# Check PHOENIX_ENABLED=true
echo $PHOENIX_ENABLED

# Restart worker after enabling Phoenix
```

---

## Limitaciones Conocidas

1. **Detección táctica limitada**: Solo pieza colgada, fork, mate perdido
   - Patrones sutiles (clavadas, desviaciones) fuera de alcance
   - Basado en heurísticas geométricas, no ML

2. **Single worker**: No horizontal scaling
   - Para producción: múltiples workers + Redis Cluster

3. **No autenticación**: API pública sin auth
   - Agregar API keys o OAuth para producción

4. **Polling status**: No webhooks/WebSockets
   - Cliente debe poll GET /jobs/{id} cada N segundos

5. **Sin rate limiting**: API endpoints sin throttling
   - Agregar rate limiter (FastAPI middleware)

---

## Licencia

MIT
