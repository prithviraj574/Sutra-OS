#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
ZONE="${GCP_COMPUTE_ZONE:-${GCP_ZONE:-us-central1-a}}"
HOST_NAME="${GCP_RUNTIME_HOST_INSTANCE_NAME:-sutra-firecracker-host}"
HOST_MANAGER_PORT="${HOST_MANAGER_PORT:-8787}"

gcloud compute ssh \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  "$HOST_NAME" \
  --tunnel-through-iap \
  --command="set -e; systemctl is-active sutra-host-manager; curl -fsS http://127.0.0.1:${HOST_MANAGER_PORT}/healthz"
