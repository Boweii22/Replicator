#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT to the target project ID}"
REGION="${GOOGLE_CLOUD_LOCATION:-europe-west1}"
TAG="$(git rev-parse --short HEAD)"
IMAGE="${REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/replicator/app:${TAG}"

gcloud config set project "${GOOGLE_CLOUD_PROJECT}"
gcloud services enable cloudbuild.googleapis.com artifactregistry.googleapis.com run.googleapis.com
terraform -chdir=infra init
WORKSPACE="$(printf '%s' "${GOOGLE_CLOUD_PROJECT}" | tr -c '[:alnum:]_-' '-')"
terraform -chdir=infra workspace select "${WORKSPACE}" || terraform -chdir=infra workspace new "${WORKSPACE}"
terraform -chdir=infra apply -auto-approve \
  -target=google_project_service.apis \
  -target=google_artifact_registry_repository.images \
  -var="project_id=${GOOGLE_CLOUD_PROJECT}" -var="region=${REGION}" -var="image=${IMAGE}"
gcloud builds submit --region="${REGION}" --config=cloudbuild.yaml --substitutions="_IMAGE=${IMAGE}" .
terraform -chdir=infra apply -auto-approve \
  -var="project_id=${GOOGLE_CLOUD_PROJECT}" -var="region=${REGION}" -var="image=${IMAGE}"

echo "Deployment complete. API URL:"
terraform -chdir=infra output -raw api_url
