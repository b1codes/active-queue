#!/usr/bin/env bash
# Run the k6 API load test (loadtest/api.js). See docs/testing.md#performance-and-load-tests.
#
#   loadtest/run.sh local|smoke   Starts the API under uvicorn against the test emulators
#                                 (run it inside `firebase emulators:exec`, as `make
#                                 load-test` does), mints emulator tokens, runs k6.
#                                 With $LOAD_API_URL it targets that API instead of starting
#                                 one (scripts/container-perf.sh runs it against the image).
#   loadtest/run.sh staging       Runs against $STAGING_API_URL with real ID tokens, signed
#                                 as $LOAD_SIGNER (needs gcloud and $FIREBASE_WEB_API_KEY).
#
# k6 runs from a pinned Docker image. Results land in $LOAD_OUT (default loadtest/out):
# summary.json and the console summary. Exits non-zero when any threshold fails.
set -euo pipefail

PROFILE="${1:-local}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${LOAD_OUT:-$ROOT/loadtest/out}"
USERS="${LOAD_USERS:-20}"   # journey users; one more is minted for the abuser
PORT="${LOAD_PORT:-8089}"
K6_IMAGE="grafana/k6:1.0.0"
mkdir -p "$OUT"

api_pid=""
# shellcheck disable=SC2317  # runs from the EXIT trap
cleanup() {
  if [[ -n "$api_pid" ]]; then
    kill "$api_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

case "$PROFILE" in
  local|smoke)
    : "${FIRESTORE_EMULATOR_HOST:?run inside firebase emulators:exec (see make load-test)}"
    : "${FIREBASE_AUTH_EMULATOR_HOST:?run inside firebase emulators:exec}"
    project="${GCLOUD_PROJECT:-demo-activequeue-local}"
    # Start from empty emulators, so every run measures the same data.
    curl -sf -X DELETE "http://$FIRESTORE_EMULATOR_HOST/emulator/v1/projects/$project/databases/(default)/documents" >/dev/null
    curl -sf -X DELETE "http://$FIREBASE_AUTH_EMULATOR_HOST/emulator/v1/projects/$project/accounts" >/dev/null
    target="${LOAD_API_URL:-}"
    if [[ -z "$target" ]]; then
      # TRUSTED_PROXY_HOPS=1 is what Cloud Run runs with: the client address is the last
      # X-Forwarded-For entry. k6 sends one per user, as Cloud Run's front end would.
      (cd "$ROOT/backend" && ENV=local CONTENT_PROVIDER=fixture TRUSTED_PROXY_HOPS=1 \
        LOG_LEVEL=WARNING exec uv run --frozen uvicorn app.main:app --host 0.0.0.0 \
        --port "$PORT" --no-access-log) > "$OUT/api.log" 2>&1 &
      api_pid=$!
      target="http://127.0.0.1:$PORT"
    fi
    for _ in $(seq 1 60); do
      curl -sf "$target/health" >/dev/null && break
      sleep 1
    done
    curl -sf "$target/health" >/dev/null || { cat "$OUT/api.log" 2>/dev/null; exit 1; }
    python3 "$ROOT/loadtest/tokens.py" --users $((USERS + 1)) --auth emulator \
      --auth-emulator-host "$FIREBASE_AUTH_EMULATOR_HOST" --out "$OUT/tokens.json"
    spoof=1
    # The emulator has no indexes: every query scans its whole collection, so query time
    # grows with the total data. Small feeds keep that out of the measurement. Reads per
    # request at scale are held exactly by tests/emulator/test_read_budgets_emulator.py.
    playlist="fixture-small-playlist"
    ;;
  staging)
    : "${STAGING_API_URL:?}" "${LOAD_SIGNER:?}" "${FIREBASE_WEB_API_KEY:?}"
    # Staging shares one address (ours) and its 300/min per-IP budget across all users.
    USERS="${LOAD_USERS:-6}"
    python3 "$ROOT/loadtest/tokens.py" --users $((USERS + 1)) --auth custom-token \
      --uid-prefix load-test-staging --signer "$LOAD_SIGNER" \
      --firebase-api-key "$FIREBASE_WEB_API_KEY" --out "$OUT/tokens.json"
    target="$STAGING_API_URL"
    spoof=0
    playlist="${LOAD_PLAYLIST:?a small public YouTube playlist ID for the load users}"
    ;;
  *) echo "usage: $0 local|smoke|staging" >&2; exit 2 ;;
esac

# Linux (CI) shares the host network; Docker Desktop reaches the host by name.
network=(--network host)
if [[ "$(uname)" == "Darwin" && "$target" == http://127.0.0.1:* ]]; then
  network=()
  target="${target/127.0.0.1/host.docker.internal}"
fi

docker run --rm ${network[@]+"${network[@]}"} --user "$(id -u):$(id -g)" -v "$ROOT/loadtest:/scripts:ro" -v "$OUT:/out" \
  -e BASE_URL="$target" -e PROFILE="$PROFILE" -e SPOOF_IPS="$spoof" -e PLAYLIST="$playlist" \
  -e TOKENS=/out/tokens.json "$K6_IMAGE" run --quiet --summary-export /out/summary.json \
  /scripts/api.js 2>&1 | tee "$OUT/k6.log"
exit "${PIPESTATUS[0]}"
