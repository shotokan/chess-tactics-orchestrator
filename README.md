# Chess Tactics Orchestrator

Sistema multi-agente asíncrono para análisis de partidas de ajedrez con Lichess + LLM.

Pregunta en lenguaje natural _"¿Cómo me va con la Siciliana con negras?"_ y obtén análisis completo:
- Datos reales de Lichess API
- Métricas (winrate, blunders, finales)
- Interpretación con Gemini LLM
- Validación supervisada con HITL (Human-in-the-Loop)

---

## 🚀 Quick Start

### 1. Pre-requisitos

**Instalar:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [uv](https://docs.astral.sh/uv/) (package manager Python)
- [Stockfish](https://stockfishchess.org/download/) chess engine

**Mac (Homebrew):**
```bash
brew install uv stockfish
```

**Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo apt install stockfish
```

### 2. Clonar Repositorio

```bash
git clone https://github.com/TU_USUARIO/chess-tactics-orchestrator.git
cd chess-tactics-orchestrator
```

### 3. Instalar Dependencias

```bash
export PATH="$HOME/.local/bin:$PATH"
uv sync
```

### 4. Configurar Credenciales

**Crear archivo `.env`:**
```bash
cp .env.example .env
```

**Editar `.env` y completar:**
```bash
# REQUIRED: Obtener en https://aistudio.google.com/app/apikey
GEMINI_API_KEY=tu_clave_aqui

# OPTIONAL: Obtener en https://lichess.org/account/oauth/token
LICHESS_API_TOKEN=tu_token_aqui

# REQUIRED: Path a Stockfish
# Mac: /opt/homebrew/bin/stockfish
# Linux: /usr/bin/stockfish
STOCKFISH_PATH=/opt/homebrew/bin/stockfish
```

**Crear scripts de ejecución:**
```bash
# Copiar templates
cp run_api.sh.example run_api.sh
cp run_worker.sh.example run_worker.sh

# Editar y completar credenciales
nano run_api.sh     # Pegar GEMINI_API_KEY, LICHESS_API_TOKEN, STOCKFISH_PATH
nano run_worker.sh  # Pegar las mismas variables

# Dar permisos de ejecución
chmod +x run_api.sh run_worker.sh
```

### 5. Iniciar Sistema

**Terminal 1 - Services (Redis + Phoenix):**
```bash
docker-compose up -d
```

Verifica:
```bash
docker ps
# Debe mostrar:
# - chess-tactics-redis (puerto 6379)
# - chess-tactics-phoenix (puerto 6006)
```

**Terminal 2 - API:**
```bash
./run_api.sh
```

Espera ver:
```
✓ Connected to Redis
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Terminal 3 - Worker:**
```bash
./run_worker.sh
```

Espera ver:
```
🚀 Starting job worker...
  Polling queue: job_queue
```

### 6. Crear Job

**Terminal 4:**
```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "user_request": "¿cómo me va con la siciliana con negras?",
    "metadata": {"username": "isabido86"}
  }'
```

**Copiar `job_id` del response:**
```json
{
  "job_id": "abc123-uuid-here",
  "status": "queued",
  ...
}
```

### 7. Ver Progreso

**Poll status cada 5s:**
```bash
JOB_ID="abc123-uuid-here"  # Reemplazar con tu job_id

watch -n 5 "curl -s http://localhost:8000/api/jobs/$JOB_ID | jq '.status'"
```

**Estados:**
1. `queued` → En cola
2. `processing` → Worker ejecutando
3. `waiting_approval` → **Pausado en HITL** (ver análisis parcial)
4. `completed` → Finalizado

### 8. Aprobar HITL

Cuando `status == "waiting_approval"`, ver resultado parcial:
```bash
curl -s http://localhost:8000/api/jobs/$JOB_ID | jq '.result'
```

**Aprobar para continuar:**
```bash
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

O **rechazar para refinamiento:**
```bash
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": false, "feedback": "Need 20+ games"}'
```

### 9. Ver Resultado Final

Poll hasta `status == "completed"`, luego:
```bash
curl -s http://localhost:8000/api/jobs/$JOB_ID | jq '.result.final_answer'
```

---

## 📊 Observabilidad (Phoenix)

**Abrir dashboard:**
```bash
open http://localhost:6006
```

**Ver traces:**
1. Click "Traces" (sidebar)
2. Filtrar proyecto: `chess-tactics-orchestrator`
3. Inspeccionar spans:
   - `worker_process_job` (latencia total)
   - `research_agent` (Lichess API)
   - `analyst_agent → compute_metrics` (Stockfish)
   - `analyst_agent → interpret_metrics` (LLM tokens)

**Capturar screenshot para entregable:**
- Click en un trace
- Screenshot mostrando spans + tiempos

---

## 🧪 Load Testing

```bash
python load_test.py
```

Ejecuta 5 jobs concurrentes, mide latencias, genera `load_test_results.json`.

---

## 🏗️ Arquitectura

### Componentes

```
Client → FastAPI → Redis Queue → Worker → LangGraph
                      ↓             ↓
                  Checkpoints    Phoenix
```

- **FastAPI**: API REST asíncrona (puerto 8000)
- **Worker**: Background processor (asyncio)
- **Redis**: Job queue + LangGraph checkpoints
- **Phoenix**: Observabilidad OpenTelemetry (puerto 6006)
- **LangGraph**: Multi-agent orchestration
- **Gemini**: LLM (gemini-3.5-flash)
- **Stockfish**: Chess engine local

### Grafo de Agentes

```
                 ┌─────────────┐
      ┌─────────▶│  Supervisor │◀─────────┐
      │          └──────┬──────┘          │
      │                 │ routing         │
      │      ┌──────────┼──────────┐      │
      │      ▼          ▼          ▼      │
      │ Research    Analyst    HITL       │
      │      │          │          │       │
      └──────┴──────────┴──────────┘       │
        (loop back for refinement)         │
                                           ▼
                                          END
```

**Justificación topología:**
- **Routing dinámico**: Supervisor decide qué agente invocar según estado
- **Validación**: Supervisor aplica rúbrica antes de END
- **Refinamiento**: Loop back si análisis insuficiente
- **HITL**: Pausa para aprobación humana antes de entregar

### Flujo HITL

```
1. POST /jobs → queued
2. Worker: research → analyst → supervisor
3. Supervisor detecta: analysis sin aprobar
4. Graph: interrupt_before=["hitl_approval"]
5. Checkpoint saved → status=waiting_approval
6. Client poll → ve resultado parcial
7. Client POST /approve con approved=true/false
8. Worker resume desde checkpoint
9. status=completed → final_answer
```

---

## 📁 Estructura

```
src/chess_tactics_orchestrator/
├── api/
│   ├── app.py              # FastAPI app
│   └── routes/
│       ├── health.py       # GET /health
│       └── jobs.py         # CRUD + approval
├── agents/
│   ├── research_agent.py   # Lichess API
│   ├── analyst_agent.py    # Metrics + LLM
│   ├── supervisor.py       # Routing + validation
│   └── hitl_node.py        # HITL checkpoint
├── infrastructure/
│   ├── redis_client.py     # Async Redis
│   └── checkpoint.py       # RedisSaver
├── observability/
│   └── phoenix_tracer.py   # OpenTelemetry
├── models/
│   └── job.py              # Pydantic schemas
├── tools/
│   ├── lichess_client.py
│   ├── stockfish_eval.py
│   └── tactic_detector.py
├── graph.py                # LangGraph
├── state.py                # AgentState
└── worker.py               # Background processor
```

---

## 🔧 Troubleshooting

### Worker no procesa jobs

```bash
# Verificar Redis
redis-cli LLEN job_queue

# Verificar worker corriendo
ps aux | grep worker
```

### API no responde

```bash
# Verificar puerto libre
lsof -i :8000

# Reiniciar
./run_api.sh
```

### Phoenix sin traces

```bash
# Verificar PHOENIX_ENABLED=true en run_worker.sh
grep PHOENIX_ENABLED run_worker.sh

# Reiniciar worker
```

---

## 📖 Documentación Completa

- [README_API.md](README_API.md) - Endpoints, modelos, ejemplos
- [TESTING.md](TESTING.md) - Guía paso a paso con outputs esperados
- [CLAUDE.md](CLAUDE.md) - Contexto del proyecto (rúbrica)

---

## 🔒 Seguridad

**IMPORTANTE:**
- ❌ **NO** subir `run_api.sh` ni `run_worker.sh` a GitHub (contienen credentials)
- ❌ **NO** commitear `.env` (ya está en .gitignore)
- ✅ Solo subir `.env.example` y `run_*.sh.example`

**Al clonar repo:**
1. `cp .env.example .env`
2. `cp run_api.sh.example run_api.sh`
3. Editar y completar credenciales
4. Los archivos reales quedan locales (ignorados por git)

---

## 📦 Dependencias Principales

- `langgraph>=0.2.0` - Multi-agent orchestration
- `langchain-google-genai>=1.0.0` - Gemini LLM
- `fastapi>=0.109.0` - API async
- `redis[hiredis]>=5.0.0` - Queue + checkpoints
- `python-chess>=1.999` - Chess logic
- `arize-phoenix>=5.0.0` - Observability

Ver [pyproject.toml](pyproject.toml) para lista completa.

---

## 📝 Limitaciones Conocidas

1. **Single worker**: No horizontal scaling
2. **Sin autenticación**: API pública
3. **Polling**: Cliente debe poll status (no webhooks)
4. **Detección táctica limitada**: Solo pieza colgada, fork, mate perdido

Ver [README_API.md](README_API.md#limitaciones-conocidas) para detalles.

---

## 📄 Licencia

MIT
