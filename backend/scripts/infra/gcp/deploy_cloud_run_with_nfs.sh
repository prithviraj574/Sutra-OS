#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

PROJECT_ID="${PROJECT_ID:-sutra-os}"
REGION="${REGION:-us-east1}"
SERVICE_NAME="${SERVICE_NAME:-sutra-backend}"
SOURCE_DIR="${SOURCE_DIR:-${BACKEND_ROOT}}"

FILESTORE_INSTANCE="${FILESTORE_INSTANCE:-sutra-hermes-fs}"
FILESTORE_ZONE="${FILESTORE_ZONE:-us-east1-b}"
FILESTORE_SHARE_NAME="${FILESTORE_SHARE_NAME:-hermes}"

VPC_NETWORK="${VPC_NETWORK:-default}"
VPC_SUBNET="${VPC_SUBNET:-default}"

NFS_VOLUME_NAME="${NFS_VOLUME_NAME:-hermeshomes}"
NFS_MOUNT_PATH="${NFS_MOUNT_PATH:-/mnt/hermes}"
SUTRA_DEV_AUTH_BYPASS="${SUTRA_DEV_AUTH_BYPASS:-false}"
ALLOW_UNAUTHENTICATED="${ALLOW_UNAUTHENTICATED:-false}"
SUTRA_JWT_ISSUER="${SUTRA_JWT_ISSUER:-sutra-backend}"
SUTRA_JWT_AUDIENCE="${SUTRA_JWT_AUDIENCE:-sutra-api}"
SUTRA_JWT_EXPIRATION_SECONDS="${SUTRA_JWT_EXPIRATION_SECONDS:-86400}"

if [ -z "${POSTGRES_URL:-}" ]; then
  echo "POSTGRES_URL is required."
  exit 1
fi
if [ -z "${SUTRA_JWT_SECRET:-}" ]; then
  echo "SUTRA_JWT_SECRET is required."
  exit 1
fi

state="$(gcloud filestore instances describe "${FILESTORE_INSTANCE}" \
  --project "${PROJECT_ID}" \
  --zone "${FILESTORE_ZONE}" \
  --format="value(state)")"
if [ "${state}" != "READY" ]; then
  echo "Filestore instance ${FILESTORE_INSTANCE} is not READY (state=${state})."
  exit 1
fi

filestore_ip="$(gcloud filestore instances describe "${FILESTORE_INSTANCE}" \
  --project "${PROJECT_ID}" \
  --zone "${FILESTORE_ZONE}" \
  --format="value(networks.ipAddresses[0])")"
if [ -z "${filestore_ip}" ]; then
  echo "Could not resolve Filestore IP for ${FILESTORE_INSTANCE}."
  exit 1
fi

nfs_location="${filestore_ip}:/${FILESTORE_SHARE_NAME}"

remove_volume_flag=""
remove_mount_flag=""
if gcloud run services describe "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed >/dev/null 2>&1; then
  existing_volumes="$(gcloud run services describe "${SERVICE_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --platform managed \
    --format="value(spec.template.spec.volumes[].name)" || true)"
  existing_mounts="$(gcloud run services describe "${SERVICE_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --platform managed \
    --format="value(spec.template.spec.containers[0].volumeMounts[].mountPath)" || true)"

  if printf "%s" "${existing_volumes}" | tr ';' '\n' | grep -Fxq "${NFS_VOLUME_NAME}"; then
    remove_volume_flag="--remove-volume=${NFS_VOLUME_NAME}"
  fi
  if printf "%s" "${existing_mounts}" | tr ';' '\n' | grep -Fxq "${NFS_MOUNT_PATH}"; then
    remove_mount_flag="--remove-volume-mount=${NFS_MOUNT_PATH}"
  fi
fi

echo "Deploying ${SERVICE_NAME} in ${REGION} with NFS mount ${nfs_location} -> ${NFS_MOUNT_PATH}"
cmd=(
  gcloud run deploy "${SERVICE_NAME}"
  --project "${PROJECT_ID}"
  --region "${REGION}"
  --platform managed
  --source "${SOURCE_DIR}"
  --network "${VPC_NETWORK}"
  --subnet "${VPC_SUBNET}"
)
if [ "${ALLOW_UNAUTHENTICATED}" = "true" ]; then
  cmd+=(--allow-unauthenticated)
else
  cmd+=(--no-allow-unauthenticated)
fi
if [ -n "${remove_volume_flag}" ]; then
  cmd+=("${remove_volume_flag}")
fi
if [ -n "${remove_mount_flag}" ]; then
  cmd+=("${remove_mount_flag}")
fi
cmd+=(
  --add-volume "name=${NFS_VOLUME_NAME},type=nfs,location=${nfs_location}"
  --add-volume-mount "volume=${NFS_VOLUME_NAME},mount-path=${NFS_MOUNT_PATH}"
  --set-env-vars "POSTGRES_URL=${POSTGRES_URL},SUTRA_DEV_AUTH_BYPASS=${SUTRA_DEV_AUTH_BYPASS},SUTRA_HERMES_HOMES_ROOT=${NFS_MOUNT_PATH},SUTRA_JWT_SECRET=${SUTRA_JWT_SECRET},SUTRA_JWT_ISSUER=${SUTRA_JWT_ISSUER},SUTRA_JWT_AUDIENCE=${SUTRA_JWT_AUDIENCE},SUTRA_JWT_EXPIRATION_SECONDS=${SUTRA_JWT_EXPIRATION_SECONDS}"
)
"${cmd[@]}"

echo "Cloud Run deploy completed."
