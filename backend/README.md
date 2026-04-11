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

## Auth

Backend app APIs now use Sutra-issued JWT bearer tokens.

- `POST /auth/exchange` accepts a Firebase ID token and returns a Sutra access token
- Firebase verification happens only at the exchange boundary
- normal app routes such as `/me` and `/agents` expect the Sutra token, not the Firebase token
- Firebase `email_verified` is enforced during token exchange

Required settings:

- `SUTRA_JWT_SECRET`
- `SUTRA_JWT_ISSUER` (optional, defaults to `sutra-backend`)
- `SUTRA_JWT_AUDIENCE` (optional, defaults to `sutra-api`)
- `SUTRA_JWT_EXPIRATION_SECONDS` (optional, defaults to `86400`)

`SUTRA_JWT_SECRET` must be at least 32 characters long.

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

## GCP Infra Scripts

Infrastructure scripts now live in `backend/scripts/infra/gcp`.

Bootstrap deploy IAM roles (run as a project owner identity):

```bash
./scripts/infra/gcp/grant_deployer_roles.sh
```

Create Filestore and wait for readiness:

```bash
./scripts/infra/gcp/create_filestore.sh
```

Deploy Cloud Run with NFS mounted at `/mnt/hermes`:

```bash
POSTGRES_URL="postgresql://..." \
SUTRA_JWT_SECRET="at-least-32-characters-long-secret" \
./scripts/infra/gcp/deploy_cloud_run_with_nfs.sh
```

Run migrations only:

```bash
POSTGRES_URL="postgresql://..." ./scripts/infra/gcp/run_migrations.sh
```

One command for Filestore + deploy + migrations:

```bash
POSTGRES_URL="postgresql://..." \
SUTRA_JWT_SECRET="at-least-32-characters-long-secret" \
./scripts/infra/gcp/provision_and_deploy.sh
```

Fetch OpenAPI from authenticated Cloud Run (no dummy user needed):

```bash
./scripts/infra/gcp/fetch_openapi.sh
```

Notes:
- Deploy defaults to authenticated-only (`--no-allow-unauthenticated`).
- Set `ALLOW_UNAUTHENTICATED=true` only if your org policy allows public invoker.
- `SUTRA_DEV_AUTH_BYPASS` defaults to `false` in deploy script.
