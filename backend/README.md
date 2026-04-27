# Agent Runtime

Python/FastAPI reimplementation of the useful core ideas from:

- `pi-mono/packages/ai`: provider/model abstraction and streamed assistant events
- `pi-mono/packages/agent`: stateful agent abstraction, agent loop, tool execution, steering/follow-up messages, and lifecycle events

The runtime uses `POSTGRES_URL` from the repo `.env`. There is no SQLite fallback.

## Layout

- `app.py`: FastAPI app factory and router composition
- `config.py`: app infrastructure config and agent runtime defaults
- `api/`: HTTP routers, request/response schemas, API dependencies
- `agent_runtime/ai/`: LLM provider interface, model/message types, stream protocol
- `agent_runtime/agent/`: stateful `Agent`, loop, tool contracts, lifecycle events
- `agent_runtime/db.py`: SQLAlchemy models and Postgres engine setup
- `agent_runtime/service.py`: application use cases that hydrate agents and persist runs

## Run

```bash
uv sync
uv run uvicorn app:create_app --factory --reload
```

## Test

```bash
uv run pytest
```
