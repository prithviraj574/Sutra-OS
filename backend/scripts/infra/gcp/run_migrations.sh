#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
TARGET="${TARGET:-head}"

if [ -z "${POSTGRES_URL:-}" ]; then
  echo "POSTGRES_URL is required."
  exit 1
fi

echo "Running Alembic migrations to target=${TARGET}"
POSTGRES_URL="${POSTGRES_URL}" "${BACKEND_ROOT}/scripts/migrations/upgrade.sh" "${TARGET}"
echo "Migrations completed."
