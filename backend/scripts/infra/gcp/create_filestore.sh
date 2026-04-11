#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sutra-os}"
FILESTORE_INSTANCE="${FILESTORE_INSTANCE:-sutra-hermes-fs}"
FILESTORE_ZONE="${FILESTORE_ZONE:-us-east1-b}"
FILESTORE_TIER="${FILESTORE_TIER:-BASIC_HDD}"
FILESTORE_SHARE_NAME="${FILESTORE_SHARE_NAME:-hermes}"
FILESTORE_CAPACITY="${FILESTORE_CAPACITY:-1TB}"
VPC_NETWORK="${VPC_NETWORK:-default}"
WAIT_ATTEMPTS="${WAIT_ATTEMPTS:-90}"
WAIT_SECONDS="${WAIT_SECONDS:-10}"

if ! gcloud filestore instances describe "${FILESTORE_INSTANCE}" \
  --project "${PROJECT_ID}" \
  --zone "${FILESTORE_ZONE}" >/dev/null 2>&1; then
  echo "Creating Filestore instance ${FILESTORE_INSTANCE} in ${FILESTORE_ZONE}"
  gcloud filestore instances create "${FILESTORE_INSTANCE}" \
    --project "${PROJECT_ID}" \
    --zone "${FILESTORE_ZONE}" \
    --tier "${FILESTORE_TIER}" \
    --file-share "name=${FILESTORE_SHARE_NAME},capacity=${FILESTORE_CAPACITY}" \
    --network "name=${VPC_NETWORK}"
else
  echo "Filestore instance ${FILESTORE_INSTANCE} already exists."
fi

echo "Waiting for Filestore instance to become READY"
for i in $(seq 1 "${WAIT_ATTEMPTS}"); do
  state="$(gcloud filestore instances describe "${FILESTORE_INSTANCE}" \
    --project "${PROJECT_ID}" \
    --zone "${FILESTORE_ZONE}" \
    --format="value(state)")"
  ip="$(gcloud filestore instances describe "${FILESTORE_INSTANCE}" \
    --project "${PROJECT_ID}" \
    --zone "${FILESTORE_ZONE}" \
    --format="value(networks.ipAddresses[0])")"
  echo "attempt=${i} state=${state} ip=${ip}"
  if [ "${state}" = "READY" ]; then
    echo "Filestore is ready at ${ip}:/${FILESTORE_SHARE_NAME}"
    exit 0
  fi
  sleep "${WAIT_SECONDS}"
done

echo "Timed out waiting for Filestore to become READY."
exit 1
