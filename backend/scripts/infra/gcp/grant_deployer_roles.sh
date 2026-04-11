#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sutra-os}"
DEPLOYER_ACCOUNT="${DEPLOYER_ACCOUNT:-888525205099-compute@developer.gserviceaccount.com}"

ROLES=(
  "roles/run.admin"
  "roles/artifactregistry.admin"
  "roles/cloudbuild.builds.editor"
  "roles/storage.admin"
  "roles/file.editor"
  "roles/logging.viewer"
)

for role in "${ROLES[@]}"; do
  echo "Granting ${role} to ${DEPLOYER_ACCOUNT} on ${PROJECT_ID}"
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${DEPLOYER_ACCOUNT}" \
    --role="${role}" \
    --quiet >/dev/null
done

echo "Role bootstrap completed."
