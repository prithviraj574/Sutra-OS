#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"

"${SCRIPT_DIR}/create_filestore.sh"
"${SCRIPT_DIR}/deploy_cloud_run_with_nfs.sh"

if [ "${RUN_MIGRATIONS}" = "true" ]; then
  "${SCRIPT_DIR}/run_migrations.sh"
fi
