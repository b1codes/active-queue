#!/usr/bin/env bash
# Start the API image against the running test emulators and run the post-deploy smoke
# check against it. Run inside `firebase emulators:exec` (see `make test-container` and
# the `container` job in ci.yml).
#
#   scripts/container-smoke.sh <image>
#
# The container runs read-only (plus a tmpfs /tmp), so an image that tries to install or
# write anything at startup fails here instead of on a Cloud Run cold start.
set -euo pipefail

IMAGE="${1:?usage: $0 <image>}"
NAME="activequeue-api-smoke-$$"
FIRESTORE="${FIRESTORE_EMULATOR_HOST:-127.0.0.1:9190}"
AUTH="${FIREBASE_AUTH_EMULATOR_HOST:-127.0.0.1:9199}"

if [[ "$(uname -s)" == "Linux" ]]; then
  # The emulators listen on the host's loopback; share the host network.
  net=(--network host)
  port=8080
  in_container() { echo "$1"; }
else
  # Docker Desktop: reach the host through host.docker.internal and publish a free port
  # (8080 is often taken on a dev machine).
  port="${SMOKE_PORT:-18080}"
  net=(-p "127.0.0.1:${port}:8080")
  in_container() { echo "host.docker.internal:${1##*:}"; }
fi

cleanup() {
  status=$?
  if [[ $status -ne 0 ]]; then
    echo "--- container logs ---"
    docker logs "$NAME" 2>&1 | tail -50 || true
  fi
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  exit $status
}
trap cleanup EXIT

docker run -d --name "$NAME" "${net[@]}" --read-only --tmpfs /tmp \
  -e ENV=local \
  -e GCP_PROJECT_ID=demo-activequeue-local \
  -e CONTENT_PROVIDER=fixture \
  -e FIRESTORE_EMULATOR_HOST="$(in_container "$FIRESTORE")" \
  -e FIREBASE_AUTH_EMULATOR_HOST="$(in_container "$AUTH")" \
  "$IMAGE" >/dev/null

python3 "$(dirname "$0")/smoke_test.py" "http://127.0.0.1:${port}" \
  --auth emulator --auth-emulator-host "$AUTH" --wait 60
