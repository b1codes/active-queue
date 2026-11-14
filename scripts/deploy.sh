#!/usr/bin/env bash
# ActiveQueue deployment (SPEC §4.9, §10.5; ClickUp 86bcxruyn, 86bcxrv0z).
#
#   scripts/deploy.sh dev|staging|prod
#
# 1. Refuses unless the working tree is clean and CI passed on a push of this commit.
# 2. Preflight: the inputs the deploy and the smoke check need are present.
# 3. Builds the API image for this commit and deploys it by digest, never by a mutable tag.
# 4. Deploys Firestore rules and indexes.
# 5. Plans Terraform, shows the plan, and applies exactly that plan once you confirm it.
# 6. Runs scripts/smoke_test.py against the service. If the smoke check fails, traffic goes
#    back to the revision that was serving before, and the script exits non-zero.
#
# Environment:
#   FIREBASE_WEB_API_KEY          Web API key of the env's Firebase project (smoke sign-in)
#   TF_VAR_google_oauth_client_id Google OAuth client ID for Identity Platform
#   TF_VAR_google_oauth_client_secret, TF_VAR_apple_client_secret
#                                 Read from Secret Manager (google-oauth-client-secret-<env>,
#                                 apple-oauth-client-secret-<env>) when not set
#   TF_VAR_smoke_test_signers     e.g. '["user:you@example.com"]' (who may sign the smoke
#                                 test's custom token; see docs/deployment)
#   REGION                        default us-central1
set -euo pipefail

ENV="${1:-}"
REGION="${REGION:-us-central1}"

if [[ ! "$ENV" =~ ^(dev|staging|prod)$ ]]; then
  echo "Usage: $0 dev|staging|prod" >&2
  exit 1
fi

cd "$(dirname "$0")/.."

PROJECT_ID="activequeue-${ENV}"
SERVICE="activequeue-api-${ENV}"
REPOSITORY="activequeue-api-${ENV}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}"
SMOKE_SIGNER="activequeue-smoke-${ENV}@${PROJECT_ID}.iam.gserviceaccount.com"
TF_DIR="infra/environments/${ENV}"
PLAN_FILE="$(mktemp -d)/deploy.tfplan"

log() { echo "--> $*"; }
die() { echo "error: $*" >&2; exit 1; }

confirm() {
  local answer
  echo
  read -r -p "$1 Type '${ENV}' to continue: " answer || true
  [[ "$answer" == "$ENV" ]] || die "not confirmed; nothing more was changed."
}

terraform_plan() {
  terraform -chdir="$TF_DIR" plan -input=false -out="$PLAN_FILE" \
    -var "container_image=$1" "${@:2}"
}

echo "=== Deploying ActiveQueue to ${ENV} (project ${PROJECT_ID}) ==="

for tool in gcloud firebase terraform gh python3; do
  command -v "$tool" >/dev/null || die "$tool is not on PATH."
done

# --- 1. Only deploy a commit CI passed --------------------------------------------------
COMMIT_SHA="$(git rev-parse HEAD)"
[[ -z "$(git status --porcelain)" ]] || die "working tree has uncommitted changes."
log "Checking that CI passed for ${COMMIT_SHA}..."
CI_SUCCESSES="$(gh run list --workflow CI --commit "${COMMIT_SHA}" --event push \
  --json conclusion --jq '[.[] | select(.conclusion == "success")] | length')"
if [[ "${CI_SUCCESSES}" == "0" ]]; then
  die "no successful CI run on a push for ${COMMIT_SHA}. Merge to main (or push the commit) and wait for CI Passed."
fi

# --- 2. Preflight -------------------------------------------------------------------------
log "Preflight checks..."
[[ -n "${FIREBASE_WEB_API_KEY:-}" ]] || die "FIREBASE_WEB_API_KEY is not set (needed for the smoke check)."
[[ -n "${TF_VAR_google_oauth_client_id:-}" ]] || die "TF_VAR_google_oauth_client_id is not set."

secret_value() {
  gcloud secrets versions access latest --secret "$1" --project "$PROJECT_ID" 2>/dev/null
}
if [[ -z "${TF_VAR_google_oauth_client_secret:-}" ]]; then
  TF_VAR_google_oauth_client_secret="$(secret_value "google-oauth-client-secret-${ENV}")" ||
    die "set TF_VAR_google_oauth_client_secret or add a version to secret google-oauth-client-secret-${ENV}."
  export TF_VAR_google_oauth_client_secret
fi
if [[ -z "${TF_VAR_apple_client_secret:-}" ]]; then
  TF_VAR_apple_client_secret="$(secret_value "apple-oauth-client-secret-${ENV}")" ||
    die "set TF_VAR_apple_client_secret or add a version to secret apple-oauth-client-secret-${ENV}."
  export TF_VAR_apple_client_secret
fi

# Cloud Run can't start a revision whose secret reference has no version.
if gcloud secrets describe "youtube-api-key-${ENV}" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud secrets versions list "youtube-api-key-${ENV}" --project "$PROJECT_ID" \
    --filter "state=ENABLED" --limit 1 --format "value(name)" | grep -q . ||
    die "secret youtube-api-key-${ENV} has no enabled version; add one before deploying."
fi

# Check now that we can sign the smoke test's token, not after the deploy (where a
# permissions problem would look like a failed deploy and trigger a rollback).
if gcloud iam service-accounts describe "$SMOKE_SIGNER" --project "$PROJECT_ID" >/dev/null 2>&1; then
  probe_dir="$(mktemp -d)"
  now="$(date +%s)"
  printf '{"iss":"%s","sub":"%s","aud":"preflight","iat":%s,"exp":%s}' \
    "$SMOKE_SIGNER" "$SMOKE_SIGNER" "$now" "$((now + 60))" >"$probe_dir/claims.json"
  gcloud iam service-accounts sign-jwt --iam-account "$SMOKE_SIGNER" \
    "$probe_dir/claims.json" "$probe_dir/out.jwt" >/dev/null 2>&1 ||
    die "you can't sign JWTs as ${SMOKE_SIGNER}. Add yourself to TF_VAR_smoke_test_signers and deploy, or ask someone listed there."
  rm -rf "$probe_dir"
else
  echo "    (first deploy: ${SMOKE_SIGNER} doesn't exist yet; the smoke check will need"
  echo "     TF_VAR_smoke_test_signers to include you)"
fi

terraform -chdir="$TF_DIR" init -input=false -lockfile=readonly >/dev/null

# --- 3. Build and push the image for this commit -----------------------------------------
if ! gcloud artifacts repositories describe "$REPOSITORY" --location "$REGION" \
  --project "$PROJECT_ID" >/dev/null 2>&1; then
  log "First deploy: creating the Artifact Registry repository with Terraform..."
  terraform_plan "${REGISTRY}/api@sha256:$(printf '0%.0s' {1..64})" \
    -target "module.${ENV}_app.google_artifact_registry_repository.api_repo"
  terraform -chdir="$TF_DIR" show "$PLAN_FILE"
  confirm "Apply this targeted plan (the image repository only)?"
  terraform -chdir="$TF_DIR" apply -input=false "$PLAN_FILE"
fi

log "Building ${REGISTRY}/api:${COMMIT_SHA}..."
gcloud builds submit backend/ --tag "${REGISTRY}/api:${COMMIT_SHA}" --project "$PROJECT_ID"
DIGEST="$(gcloud artifacts docker images describe "${REGISTRY}/api:${COMMIT_SHA}" \
  --project "$PROJECT_ID" --format 'value(image_summary.digest)')"
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || die "couldn't read the pushed image's digest (got '${DIGEST}')."
IMAGE="${REGISTRY}/api@${DIGEST}"
log "Image: ${IMAGE}"

# --- 4. Firestore rules and indexes ------------------------------------------------------
# Before the new revision, so queries it adds have their indexes (they build in the
# background; check the console if a new index is large).
log "Deploying Firestore rules and indexes..."
firebase deploy --only firestore:rules,firestore:indexes --project "$PROJECT_ID"

# --- 5. Reviewed Terraform plan ----------------------------------------------------------
PREVIOUS_REVISION="$(gcloud run services describe "$SERVICE" --region "$REGION" \
  --project "$PROJECT_ID" --format 'value(status.latestReadyRevisionName)' 2>/dev/null || true)"

log "Planning Terraform for ${ENV}..."
terraform_plan "$IMAGE"
terraform -chdir="$TF_DIR" show "$PLAN_FILE"
confirm "Apply this plan to ${ENV}?"
terraform -chdir="$TF_DIR" apply -input=false "$PLAN_FILE"

# --- 6. Smoke check, roll back on failure ------------------------------------------------
SERVICE_URL="$(terraform -chdir="$TF_DIR" output -raw cloud_run_url)"
log "Smoke-checking ${SERVICE_URL}..."
if python3 scripts/smoke_test.py "$SERVICE_URL" \
  --auth custom-token --signer "$SMOKE_SIGNER" --firebase-api-key "$FIREBASE_WEB_API_KEY" \
  --uid "smoke-test-${ENV}" --project "$PROJECT_ID" --expect-verified-tokens; then
  echo "=== ActiveQueue ${COMMIT_SHA:0:12} is live in ${ENV} ==="
  exit 0
fi

if [[ -n "$PREVIOUS_REVISION" ]]; then
  echo "Smoke check failed: sending all traffic back to ${PREVIOUS_REVISION}." >&2
  gcloud run services update-traffic "$SERVICE" --region "$REGION" --project "$PROJECT_ID" \
    --to-revisions "${PREVIOUS_REVISION}=100"
  echo "Rolled back. The failed revision stays deployed without traffic. The module declares" >&2
  echo "100% to the latest revision, so the next deploy's plan moves traffic forward again." >&2
else
  echo "Smoke check failed on the first deploy of ${ENV}; there is no revision to roll back to." >&2
fi
exit 1
