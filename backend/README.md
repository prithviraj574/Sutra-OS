# Backend (Data Model + Hermes Import Bridge)

## Setup

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync
```

Copy the shared app template when starting locally:

```bash
cp .env.example .env
```

## Local Postgres (recommended for migrations)

```bash
./scripts/db/up.sh
```

Default local URL:

```text
postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sutra
```

You can override with `POSTGRES_URL` (or `DATABASE_URL`).

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
