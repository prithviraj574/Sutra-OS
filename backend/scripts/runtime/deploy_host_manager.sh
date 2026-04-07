#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
ZONE="${GCP_COMPUTE_ZONE:-${GCP_ZONE:-us-central1-a}}"
HOST_NAME="${GCP_RUNTIME_HOST_INSTANCE_NAME:-sutra-firecracker-host}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../" && pwd)"

gcloud compute ssh \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  "$HOST_NAME" \
  --command="mkdir -p /opt/sutra/host_manager"

gcloud compute scp \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  "$REPO_ROOT/host_manager/main.py" \
  "$REPO_ROOT/host_manager/config.py" \
  "$REPO_ROOT/host_manager/firecracker.py" \
  "$REPO_ROOT/host_manager/gcp_disk.py" \
  "$REPO_ROOT/host_manager/schemas.py" \
  "$REPO_ROOT/host_manager/__init__.py" \
  "${HOST_NAME}:/opt/sutra/host_manager/"

gcloud compute ssh \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  "$HOST_NAME" \
  --command="systemctl restart sutra-host-manager && systemctl status sutra-host-manager --no-pager"
