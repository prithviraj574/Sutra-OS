#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
ZONE="${GCP_COMPUTE_ZONE:-${GCP_ZONE:-us-central1-a}}"
HOST_NAME="${GCP_RUNTIME_HOST_INSTANCE_NAME:-sutra-firecracker-host}"
SA_NAME="${HOST_NAME}-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
MACHINE_TYPE="${GCP_MACHINE_TYPE:-n2-standard-8}"
IMAGE_FAMILY="${GCP_IMAGE_FAMILY:-debian-12}"
IMAGE_PROJECT="${GCP_IMAGE_PROJECT:-debian-cloud}"
BOOT_DISK_SIZE="${GCP_BOOT_DISK_SIZE:-50GB}"
MIN_CPU_PLATFORM="${GCP_MIN_CPU_PLATFORM:-}"
NO_ADDRESS="${GCP_NO_ADDRESS:-true}"
NESTED_VIRT_MODE="${GCP_NESTED_VIRT_MODE:-flag}"
CUSTOM_IMAGE_NAME="${GCP_NESTED_VIRT_IMAGE_NAME:-${HOST_NAME}-nested-vmx}"
SOURCE_DISK_NAME="${GCP_NESTED_VIRT_SOURCE_DISK_NAME:-${CUSTOM_IMAGE_NAME}-src}"
IAP_SSH_FIREWALL_RULE="${GCP_IAP_SSH_FIREWALL_RULE:-sutra-allow-iap-ssh}"

require_nested_virt_policy() {
  local policy_output
  if ! policy_output="$(gcloud resource-manager org-policies describe \
    constraints/compute.disableNestedVirtualization \
    --project="$PROJECT_ID" \
    --effective 2>/dev/null)"; then
    echo "Could not read compute.disableNestedVirtualization policy for project ${PROJECT_ID}." >&2
    echo "Nested virtualization must be allowed before provisioning a Firecracker host." >&2
    exit 1
  fi

  if grep -q "enforced: true" <<<"$policy_output"; then
    echo "Nested virtualization is disabled for project ${PROJECT_ID} by org policy." >&2
    echo "Ask a project/org admin to disable enforcement for compute.disableNestedVirtualization first." >&2
    exit 1
  fi
}

ensure_nested_vmx_image() {
  if gcloud compute images describe "$CUSTOM_IMAGE_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
    return 0
  fi

  gcloud compute disks create "$SOURCE_DISK_NAME" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --image-project="$IMAGE_PROJECT" \
    --image-family="$IMAGE_FAMILY"

  gcloud compute images create "$CUSTOM_IMAGE_NAME" \
    --project="$PROJECT_ID" \
    --source-disk="$SOURCE_DISK_NAME" \
    --source-disk-zone="$ZONE" \
    --licenses="https://www.googleapis.com/compute/v1/projects/vm-options/global/licenses/enable-vmx"

  gcloud compute disks delete "$SOURCE_DISK_NAME" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --quiet
}

gcloud services enable --project="$PROJECT_ID" compute.googleapis.com iap.googleapis.com iam.googleapis.com

require_nested_virt_policy

if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" \
    --project="$PROJECT_ID" \
    --display-name="Sutra Runtime Host"
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/compute.instanceAdmin.v1" \
  --quiet >/dev/null

if ! gcloud compute firewall-rules describe "$IAP_SSH_FIREWALL_RULE" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute firewall-rules create "$IAP_SSH_FIREWALL_RULE" \
    --project="$PROJECT_ID" \
    --allow=tcp:22 \
    --direction=INGRESS \
    --source-ranges=35.235.240.0/20
fi

CREATE_ARGS=(
  "$HOST_NAME"
  --project="$PROJECT_ID"
  --zone="$ZONE"
  --machine-type="$MACHINE_TYPE"
  --boot-disk-size="$BOOT_DISK_SIZE"
  --service-account="$SA_EMAIL"
  --scopes="cloud-platform"
)

if [[ "$NESTED_VIRT_MODE" == "license" ]]; then
  ensure_nested_vmx_image
  CREATE_ARGS+=(--image="$CUSTOM_IMAGE_NAME")
  if [[ -z "$MIN_CPU_PLATFORM" ]]; then
    MIN_CPU_PLATFORM="Intel Haswell"
  fi
else
  CREATE_ARGS+=(--image-family="$IMAGE_FAMILY" --image-project="$IMAGE_PROJECT" --enable-nested-virtualization)
fi

if [[ "$NO_ADDRESS" == "true" ]]; then
  CREATE_ARGS+=(--no-address)
fi

if [[ -n "$MIN_CPU_PLATFORM" ]]; then
  CREATE_ARGS+=(--min-cpu-platform="$MIN_CPU_PLATFORM")
fi

if gcloud compute instances describe "$HOST_NAME" --project="$PROJECT_ID" --zone="$ZONE" >/dev/null 2>&1; then
  echo "Instance $HOST_NAME already exists in $ZONE"
  exit 0
fi

gcloud compute instances create "${CREATE_ARGS[@]}"
