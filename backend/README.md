# Backend (FastAPI + Data Model + Hermes Import Bridge)

## Setup

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync
```

Copy the shared app template when starting locally:

```bash
cp .env.example .env
```

## Database

Set a single `POSTGRES_URL` in `backend/.env` (Neon recommended).

## Hermes Homes

Set `SUTRA_HERMES_HOMES_ROOT` to the root of the mounted Hermes storage.

- Local default: if unset, backend uses `backend/.sutra/hermes-homes`
- Cloud Run + Filestore: set `SUTRA_HERMES_HOMES_ROOT=/mnt/hermes`
- Agent homes are then created under `/mnt/hermes/.hermes/profiles/agent-<uuid>`

When `SUTRA_HERMES_HOMES_ROOT` is explicitly set, the app now fails fast on startup if that path is missing or not writable. This helps catch a missing Filestore mount early instead of silently writing to the container filesystem.

## Migrations

Create migration:

```bash
./scripts/migrations/create.sh "describe change"
```

Upgrade:

```bash
./scripts/migrations/upgrade.sh
```

Downgrade one step:

```bash
./scripts/migrations/downgrade.sh
```

Downgrade to a specific revision:

```bash
./scripts/migrations/downgrade.sh <revision>
```

## Layout

- `app/models/`: SQLModel entities (`models.py`, `enums.py`)
- `app/db/`: database engine/session boundary
- `app/hermes/`: Hermes library integration boundary
- `migrations/`: Alembic migrations
- `hermes_agent/`: backward-compatible import shim

## Hermes Library Import

```python
from backend.app.hermes import AIAgent
```

The bridge automatically adds the repository's `hermes-agent/` path to `sys.path`.

## Run API

```bash
uvicorn app.main:app --reload --app-dir backend
```
