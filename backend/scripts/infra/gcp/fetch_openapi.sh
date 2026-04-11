#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sutra-os}"
REGION="${REGION:-us-east1}"
SERVICE_NAME="${SERVICE_NAME:-sutra-backend}"
OPENAPI_PATH="${OPENAPI_PATH:-./openapi.cloudrun.json}"

service_url="$(gcloud run services describe "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed \
  --format='value(status.url)')"
if [ -z "${service_url}" ]; then
  echo "Could not resolve Cloud Run service URL."
  exit 1
fi

token="$(gcloud auth print-identity-token --audiences="${service_url}")"
if [ -z "${token}" ]; then
  echo "Could not obtain identity token."
  exit 1
fi

curl -sS \
  -H "Authorization: Bearer ${token}" \
  "${service_url}/openapi.json" > "${OPENAPI_PATH}"

echo "OpenAPI saved to ${OPENAPI_PATH}"
