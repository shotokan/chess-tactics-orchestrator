# Orquestador Multi-Agente de Análisis de Ajedrez — Contexto del Proyecto

Este documento es el contexto de referencia para trabajar con Claude Code en este repositorio. Colócalo como `CLAUDE.md` en la raíz del repo para que se cargue automáticamente en cada sesión.

## 1. Propósito

Sistema multi-agente jerárquico que responde preguntas en lenguaje natural sobre el historial de ajedrez de un usuario en Lichess (ej. _"¿cómo me ha ido con la Siciliana últimos 3 meses?"_), combinando:

- Datos reales obtenidos vía la API pública de Lichess.
- Análisis cuantitativo (winrate, blunders, tendencias por color/tiempo de control).
- Interpretación en lenguaje natural generada por un LLM.
- Un ciclo de supervisión que valida si la respuesta es suficiente o requiere refinamiento antes de entregarla.

## 2. Rúbrica del entregable — checklist exacto

Esto es lo que se califica. Cada punto debe quedar verificable con un `ls`/`grep` rápido, no solo "en espíritu":

- [ ] **Estructura de repo**: `state.py` en la raíz, directorio `agents/` con `research_agent.py` y `analyst_agent.py`, grafo principal en `graph.py` (o `main.py`).
- [ ] **Grafo**: construido con `StateGraph` de LangGraph.
- [ ] **Supervisor**: al menos un nodo `Supervisor` que decide el flujo dinámicamente, y su función de routing devuelve un tipo `Literal[...]` usado en `add_conditional_edges`.
- [ ] **Tools**: cada agente especialista tiene al menos una herramienta funcional real (función propia o `TavilySearchResults`) — no un mock que siempre devuelve lo mismo.
- [ ] **Validación**: un nodo `Validation` explícito, o el `Supervisor` con una rúbrica personalizada en su prompt que valida los resultados de los especialistas antes de permitir `END`.
- [ ] **README** con: diagrama del grafo generado con `graph.get_graph().draw_mermaid_png()`, justificación de la topología elegida, y explicación de cómo se manejan conflictos entre agentes.

## 3. Estructura de repositorio (obligatoria, según rúbrica)

```
chess-agent-orchestrator/
├── CLAUDE.md
├── README.md                  # diagrama mermaid + justificación (§7)
├── requirements.txt
├── .env.example
├── state.py                   # AgentState y tipos compartidos
├── graph.py                   # StateGraph, nodos, conditional edges (o main.py)
├── agents/
│   ├── __init__.py
│   ├── research_agent.py      # Agente de Investigación + su tool
│   ├── analyst_agent.py       # Agente de Análisis + su tool
│   └── supervisor.py          # nodo Supervisor (routing + validación)
├── tools/
│   ├── __init__.py
│   ├── lichess_client.py      # tool real: consulta API de Lichess
│   ├── stockfish_eval.py      # tool real: evaluación de posiciones (Lichess evals -> fallback Stockfish)
│   └── tactic_detector.py     # tool real: clasifica patrones tácticos perdidos (§6)
├── assets/
│   └── graph.png              # output de draw_mermaid_png(), referenciado en README
└── tests/
    ├── test_state.py
    ├── test_research_agent.py
    ├── test_analyst_agent.py
    └── test_supervisor.py
```

Nota: la rúbrica acepta `main.py` **o** `graph.py` para el grafo principal — usamos `graph.py` para el grafo y un `main.py` delgado como entry point de CLI que lo invoca, así queda claro qué es orquestación y qué es punto de entrada.

## 4. Arquitectura

```
                 ┌─────────────┐
      ┌─────────▶│  Supervisor │◀─────────┐
      │          └──────┬──────┘          │
      │                 │ routing         │
      │                 │ (Literal)       │
      │      ┌──────────┼──────────┐      │
      │      ▼          ▼          ▼      │
      │ Investigación  Análisis    END     │
      │  (research_    (analyst_          │
      │   agent.py)     agent.py)          │
      │      │          │                  │
      └──────┴──────────┴──────────────────┘
        (resultados vuelven al Supervisor)
```

- **Supervisor** (`agents/supervisor.py`): nodo con dos responsabilidades:
  1. **Routing dinámico** — función que devuelve un `Literal["research", "analyst", "end"]`, usada como `path_map` en `add_conditional_edges`.
  2. **Validación** — antes de permitir `"end"`, aplica una rúbrica (prompt con criterios explícitos, ver §6) sobre los resultados acumulados en el `state`.
- **Agente de Investigación** (`agents/research_agent.py`): usa la tool `lichess_client.py` para traer partidas reales de la API de Lichess según lo pedido (apertura, rango de fechas, color, tiempo de control).
- **Agente de Análisis** (`agents/analyst_agent.py`): usa las tools `stockfish_eval.py` (evaluación de posiciones, con fallback Lichess→Stockfish) y `tactic_detector.py` (clasificación de patrones tácticos perdidos) para calcular las métricas del §6.

## 5. Métricas del Agente de Análisis

Set definitivo, elegido para dar variedad real sin convertir la detección de patrones en el proyecto entero:

| #   | Métrica                                                        | Fuente                                                                           | Costo                              |
| --- | -------------------------------------------------------------- | -------------------------------------------------------------------------------- | ---------------------------------- |
| 1   | Winrate por apertura                                           | API de Lichess (metadata de la partida)                                          | Ninguno                            |
| 2   | Winrate por color                                              | API de Lichess (metadata)                                                        | Ninguno                            |
| 3   | Terminación de partida (tiempo / mate / abandono)              | API de Lichess (metadata)                                                        | Ninguno                            |
| 4   | Winrate por tipo de final (peones / torres / piezas menores)   | Clasificación de material final con `python-chess`                               | Bajo (sin motor)                   |
| 5   | Patrones tácticos perdidos (pieza colgada, fork, mate perdido) | Stockfish + heurísticas geométricas sobre partidas reales (`tactic_detector.py`) | Alto (requiere evaluar posiciones) |

**Sobre la métrica 5 — por qué se basa en partidas reales y no en el puzzle dashboard de Lichess:**

El endpoint `GET /api/puzzle/dashboard/{days}` de Lichess da desempeño por tema táctico (`fork`, `pin`, `doubleAttack`, etc.), pero solo si el usuario juega puzzles — es un producto separado de sus partidas reales, y no responde "en qué fallo cuando juego" sino "en qué fallo cuando resuelvo puzzles". Para basarlo en las partidas reales del usuario, el flujo es:

1. **Detectar el blunder**: evaluar cada posición con Stockfish y marcar jugadas donde el eval cae más de un umbral (ej. >150 centipawns) en contra del jugador.
2. **Comparar jugada real vs `best_move`** que sugiere Stockfish en esa posición — la diferencia es donde vive el patrón perdido.
3. **Clasificar con heurísticas geométricas usando `python-chess`** (sin ML, sin replicar el clasificador interno de Lichess), limitado a 3 patrones detectables de forma confiable:
   - **Pieza colgada**: el `best_move` es una captura hacia una casilla sin defensores (`board.attackers()`).
   - **Fork/ataque doble**: tras el `best_move`, una pieza ataca simultáneamente 2+ piezas de valor o pieza+rey (`board.attacks(square)`).
   - **Mate perdido**: Stockfish marca el `best_move` como mate en N (`score.is_mate()`) y la jugada real no lo es.
4. Se agregan conteos por tema a lo largo de las partidas analizadas: "de 12 blunders, 5 piezas colgadas, 3 forks perdidos, 2 mates perdidos, 2 sin clasificar".

Patrones más sutiles (clavadas, ataques descubiertos, desviaciones, y cualquier falla estratégica/posicional) quedan fuera de alcance — se declaran como limitación conocida en el README en vez de forzar heurísticas poco confiables. El puzzle dashboard puede integrarse como enriquecimiento **opcional**: si el usuario tiene historial de puzzles, se añade como dato complementario en `analysis_metadata`, pero nunca como la fuente principal de la métrica 5.

## 6. Esquema de State (`state.py`)

```python
from typing import TypedDict, Literal, Optional, Annotated
import operator

class Contribution(TypedDict):
    agent: str
    summary: str
    timestamp: str

class AgentState(TypedDict):
    user_request: str
    games_raw: list[dict]
    # Annotated + operator.add para que cada nodo AÑADA sin pisar lo previo
    contributions: Annotated[list[Contribution], operator.add]
    analysis_result: Optional[dict]
    analysis_metadata: dict            # ej. {"games_with_lichess_eval": 28, "games_with_stockfish_fallback": 12}
    needs_refinement: bool
    refine_target: Optional[Literal["research", "analyst"]]
    refinement_count: int              # límite duro para evitar loops infinitos (2-3)
    final_answer: Optional[str]
```

Usar `Annotated[list[Contribution], operator.add]` es importante: en LangGraph, si dos campos del state se escriben en el mismo "tick" sin un reducer, uno puede sobreescribir al otro. Con `operator.add` como reducer, cada nodo puede devolver `{"contributions": [nueva_entrada]}` y LangGraph concatena en vez de reemplazar — esto es lo que da la trazabilidad de "qué agente aportó qué" que pide la rúbrica.

## 7. Rúbrica de validación del Supervisor

El prompt del Supervisor debe incluir criterios explícitos y verificables, no solo "revisa si está bien". Ejemplo de estructura de rúbrica a poner en el prompt:

```
Evalúa el resultado del especialista contra estos criterios:
1. Completitud: ¿el número de partidas analizadas es representativo (>= 10)?
2. Relevancia: ¿los datos obtenidos corresponden a lo que pidió el usuario
   (apertura, color, rango de fechas correctos)?
3. Profundidad: ¿el análisis va más allá de un solo número agregado
   (identifica patrones, no solo winrate global)?
4. Gaps declarados: ¿el propio agente reportó limitaciones (`gaps`) que
   comprometen la respuesta?

Responde en formato estructurado:
- complete: bool
- reason: str
- refine_target: "research" | "analyst" | null
- instructions: str  (qué debe mejorar específicamente)
```

Antes de invocar esta rúbrica vía LLM, aplicar chequeos determinísticos baratos (sin LLM) como pre-filtro:

- `len(games_raw) < 10` → refinar `research` automáticamente.
- Campos `None`/vacíos en `analysis_result` → refinar `analyst` automáticamente.

Límite duro: `refinement_count` máximo 2-3. Al alcanzarlo, el Supervisor fuerza `END` y el `final_answer` debe declarar explícitamente las limitaciones (ej. "solo se encontraron 6 partidas con este filtro").

## 8. Manejo de conflictos entre agentes (para el README)

Esto responde directamente el punto de la rúbrica sobre "cómo manejas los posibles conflictos entre agentes":

- **Conflicto de recursos/orden**: el Agente de Análisis depende de que Investigación ya haya poblado `games_raw`. El Supervisor nunca rutea a `analyst` si `games_raw` está vacío (chequeo determinístico antes del routing por LLM).
- **Conflicto de interpretación**: si el Agente de Análisis reporta `answers_user_question: False` o `gaps` no vacíos, eso es una señal explícita de conflicto entre lo que se pidió y lo que se obtuvo — el Supervisor la resuelve decidiendo a quién regresar (`research` si el problema es de datos, `analyst` si el problema es de profundidad de interpretación).
- **Loops infinitos**: si Investigación y Análisis se "culpan" mutuamente en ciclos repetidos, `refinement_count` corta el ciclo y se entrega una respuesta parcial con limitaciones declaradas, en vez de colgar el sistema.
- **Fuente de verdad única**: todo el intercambio pasa por `AgentState` tipado — ningún agente lee el output crudo de otro directamente, siempre a través del state, lo que evita desincronización de formatos entre agentes.

## 9. Stack técnico

- **Orquestación**: LangGraph (`StateGraph`), Python
- **LLM**: Gemini vía API de Google (modelo pequeño/rápido tipo Haiku, para mantener costos bajos en el prototipo)
- **Tool del Agente de Investigación**: función propia contra la API pública de Lichess (`GET /api/games/user/{username}`), sin API key para datos públicos
- **Tools del Agente de Análisis**: `python-chess` + Stockfish local para evaluación de posiciones y clasificación de finales/patrones tácticos (§6)
- **Diagrama**: `graph.get_graph().draw_mermaid_png()` exportado a `assets/graph.png` e incluido en el README

## 10. Roadmap sugerido (para trabajar en pasos con Claude Code)

1. Crear `state.py` con `AgentState` y el reducer de `contributions`.
2. Crear `tools/lichess_client.py` (fetch real de partidas) y probarlo aislado, sin LLM todavía.
3. Crear `agents/research_agent.py`: usa la tool anterior, LLM interpreta la solicitud del usuario → parámetros de búsqueda.
4. Crear `tools/stockfish_eval.py` (evaluación de posiciones con fallback Lichess→Stockfish) y probar contra un puñado de partidas reales.
5. Crear `tools/tactic_detector.py`: detección de blunder + heurísticas de pieza colgada / fork / mate perdido (§6, métrica 5) y clasificación de tipo de final (métrica 4).
6. Crear `agents/analyst_agent.py`: junta las 5 métricas + interpretación LLM + autoevaluación (`gaps`, `answers_user_question`).
7. Crear `agents/supervisor.py`: función de routing con `Literal` de retorno + rúbrica de validación (reglas duras + LLM).
8. Ensamblar `graph.py` con `StateGraph`, registrar nodos, usar `add_conditional_edges` con el `Literal` del supervisor.
9. Probar el ciclo feliz (sin refinamiento) y luego casos que fuerzan refinamiento, verificando que `refinement_count` corta el loop.
10. Generar el diagrama (`draw_mermaid_png()`) y escribir el README (diagrama + justificación de topología + manejo de conflictos, ver §8; limitaciones conocidas de la detección táctica, ver §6).

## 11. Convenciones

- Comentarios, logs y mensajes de commit en **inglés**.
- Toda comunicación entre nodos vía el `AgentState` tipado — nada de variables globales ni side channels.
- Cada nodo debe ser testeable de forma aislada (inyectar un `state` de prueba y verificar el output) — de ahí el directorio `tests/`.
