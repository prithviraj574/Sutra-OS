#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ "${1:-}" = "" ]; then
  echo "Usage: ./scripts/migrations/create.sh \"migration message\""
  exit 1
fi

if [ -z "${POSTGRES_URL:-}" ]; then
  echo "POSTGRES_URL is required."
  exit 1
fi

cd "$BACKEND_ROOT"
UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run alembic revision --autogenerate -m "$1"
