#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage: ./scripts/migrate-create.sh \"migration message\""
  exit 1
fi

DEFAULT_DB_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sutra"
export POSTGRES_URL="${POSTGRES_URL:-${DATABASE_URL:-$DEFAULT_DB_URL}}"

UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run alembic revision --autogenerate -m "$1"
