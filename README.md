# TechDoc Agent

Agente de documentación técnica: le pasas documentación (de una librería o de tu proyecto) y te responde con ejemplos de código, y puede generar **diagramas** y **requisitos** a partir de ella.

> Proyecto de aprendizaje: construir un agente **desde cero**, sin frameworks de agentes, entendiendo cada pieza.

## Contenido del repositorio

El código se construye por fases siguiendo el roadmap (`docs/08-roadmap-fases.md`).

| Archivo | Para qué sirve |
|---|---|
| `AGENTS.md` | Reglas del proyecto y **mapa de ubicaciones** (dónde está cada cosa) |
| `CLAUDE.md` | Importa `AGENTS.md`; es el archivo que Claude Code lee automáticamente |
| `docs/01` … `docs/09` | Visión, requisitos, arquitectura, diseño del agente, RAG, API/MCP, evaluaciones, roadmap y decisiones |
| `src/techdoc_agent/` | Código del paquete (`config.py`, `logging_setup.py`, …) |
| `tests/` | Tests con `pytest` |
| `skills/documentacion-tecnica/SKILL.md` | La skill que se carga en el agente |
| `evals/dataset.example.jsonl` | Casos de prueba de ejemplo |
| `data/sample_docs/taskflow.md` | Documentación ficticia para probar sin material real |
| `.env.example`, `requirements.txt`, `pyproject.toml` | Configuración base |

## Instalación

Necesitas Python 3.11+ y el CLI `claude` (Claude Code) instalado y con sesión iniciada; no hace falta API key.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install python-dotenv pytest             # dependencias de las Fases 0-1
pip install -e .                             # instala el paquete en modo editable
cp .env.example .env                         # modelo por defecto: claude-haiku-5-5
pytest
```

Las dependencias se instalan por fases (ver ADR-007 en `docs/09`); `pip install -r requirements.txt` instala todas.

## Chat por consola

```bash
python -m techdoc_agent.cli
```
Comandos: `/nuevo` reinicia la conversación y `/salir` termina. Por ahora el agente solo tiene dos herramientas de juguete (`obtener_hora`, `sumar`); prueba: *"¿qué hora es y cuánto es 17+25?"*. Tras cada respuesta se muestran las herramientas usadas, su duración y los tokens.

## Estructura del núcleo (`src/techdoc_agent/core/`)

| Módulo | Responsabilidad |
|---|---|
| `llm.py` | Interfaz `LLMClient` y `ClaudeCliClient` (llama a `claude -p`, protocolo JSON de herramientas) |
| `tools.py` | Registro de herramientas y `dispatch()` que nunca lanza excepciones |
| `memory.py` | Historial por `session_id` |
| `agent.py` | Bucle del agente con tope de iteraciones y logging de cada paso |

## Configuración y logs

- Toda la configuración se lee de variables de entorno (`.env`) en `techdoc_agent.config.settings`.
- Cada evento del agente se registra como una línea JSON en `logs/agent-YYYYMMDD.jsonl` con `techdoc_agent.logging_setup.log_event(...)`.

## Estado

Fases 0 y 1 completadas. Ver el checklist de fases al inicio de `docs/08-roadmap-fases.md`.
