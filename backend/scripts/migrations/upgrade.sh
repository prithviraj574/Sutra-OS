#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

TARGET="${1:-head}"
DEFAULT_DB_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sutra"
export POSTGRES_URL="${POSTGRES_URL:-${DATABASE_URL:-$DEFAULT_DB_URL}}"

cd "$BACKEND_ROOT"
UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run alembic upgrade "$TARGET"
