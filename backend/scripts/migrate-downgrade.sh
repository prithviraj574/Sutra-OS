#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:--1}"
DEFAULT_DB_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sutra"
export POSTGRES_URL="${POSTGRES_URL:-${DATABASE_URL:-$DEFAULT_DB_URL}}"

UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run alembic downgrade "$TARGET"
