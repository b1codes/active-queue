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

# 1. Verify clean CI test suite before deployment
echo "--> Running CI local verification..."
(cd backend && uv run pytest --cov=app --cov-fail-under=80 tests/)
(cd frontend && pnpm typecheck && pnpm test)

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
