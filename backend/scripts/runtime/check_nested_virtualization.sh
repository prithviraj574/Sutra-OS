#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
ZONE="${GCP_COMPUTE_ZONE:-${GCP_ZONE:-us-central1-a}}"
HOST_NAME="${GCP_RUNTIME_HOST_INSTANCE_NAME:-sutra-firecracker-host}"

echo "Project policy:"
gcloud resource-manager org-policies describe \
  constraints/compute.disableNestedVirtualization \
  --project="$PROJECT_ID" \
  --effective

if ! gcloud compute instances describe "$HOST_NAME" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" >/dev/null 2>&1; then
  echo
  echo "Instance $HOST_NAME not found in $ZONE."
  exit 0
fi

echo
echo "Instance config:"
gcloud compute instances describe "$HOST_NAME" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --format="yaml(name,status,machineType,minCpuPlatform,advancedMachineFeatures,disks)"

echo
echo "Guest virtualization checks:"
gcloud compute ssh \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  "$HOST_NAME" \
  --tunnel-through-iap \
  --command="set -e; uname -a; echo 'vmx count:'; grep -cw vmx /proc/cpuinfo || true; echo '/dev/kvm:'; ls -l /dev/kvm || true; echo 'kvm modules:'; lsmod | grep '^kvm' || true"
