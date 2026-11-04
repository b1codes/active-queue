#!/usr/bin/env bash
set -euo pipefail

# ActiveQueue Production & Environment Deployment Script
# SPEC §4.9, §10.5 & Milestone 6 Subtask 5

ENV="${1:-dev}"
REGION="${REGION:-us-central1}"

if [[ ! "$ENV" =~ ^(dev|staging|prod)$ ]]; then
  echo "Usage: $0 [dev|staging|prod]"
  exit 1
fi

PROJECT_ID="activequeue-${ENV}"
IMAGE_TAG="us-central1-docker.pkg.dev/${PROJECT_ID}/activequeue-api-${ENV}/api:latest"

echo "=== Deploying ActiveQueue to Environment: ${ENV} (Project: ${PROJECT_ID}) ==="

# 1. Only deploy a commit that CI has already passed (ClickUp 86bcxruyn).
#    Re-running tests locally proves nothing about what CI saw; the gate is the green
#    "CI" workflow run for this exact commit on GitHub.
COMMIT_SHA="$(git rev-parse HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing to deploy: working tree has uncommitted changes." >&2
  exit 1
fi
echo "--> Checking that CI passed for ${COMMIT_SHA}..."
CI_CONCLUSION="$(gh run list --workflow CI --commit "${COMMIT_SHA}" --event push \
  --json conclusion --jq '[.[] | select(.conclusion == "success")] | length')"
if [[ "${CI_CONCLUSION}" == "0" ]]; then
  echo "Refusing to deploy ${COMMIT_SHA}: no successful CI run on a push for this commit." >&2
  echo "Merge to main (or push the commit) and wait for CI Passed first." >&2
  exit 1
fi

# 2. Build & Submit Container to Artifact Registry
echo "--> Building and pushing Docker container image: ${IMAGE_TAG}..."
gcloud builds submit backend/ \
  --tag "${IMAGE_TAG}" \
  --project "${PROJECT_ID}"

# 3. Deploy Firestore Rules and Composite Indexes
echo "--> Deploying Firestore security rules and composite indexes..."
firebase deploy --only firestore:rules,firestore:indexes --project "${PROJECT_ID}"

# 4. Apply Terraform Infrastructure Configuration
echo "--> Applying Terraform configuration for ${ENV}..."
(cd "infra/environments/${ENV}" && terraform init && terraform apply -auto-approve)

echo "=== ActiveQueue Deployment to ${ENV} Complete! ==="
