#!/usr/bin/env bash
# Cold start, memory and load for the API image under Cloud Run's limits (ClickUp 86bcxrv0j).
# Run inside `firebase emulators:exec`, as the `container` job in ci.yml and
# `make test-container` do.
#
#   scripts/container-perf.sh <image>
#
# 1. Starts the image read-only with Cloud Run's 1 vCPU and 512 MiB
#    (infra/modules/activequeue_app/main.tf) and times docker run -> first 200 from
#    /healthz (the startup probe's path), then the first signed-in request, which pays
#    for the lazy Firebase Admin and Firestore client setup.
# 2. Runs the k6 smoke profile (loadtest/api.js) against it, sampling its memory.
# 3. Fails when a budget below is blown, the container was OOM-killed, or k6 fails.
set -euo pipefail

IMAGE="${1:?usage: $0 <image>}"
NAME="activequeue-api-perf-$$"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${LOAD_OUT:-$ROOT/loadtest/out}"
FIRESTORE="${FIRESTORE_EMULATOR_HOST:-127.0.0.1:9190}"
AUTH="${FIREBASE_AUTH_EMULATOR_HOST:-127.0.0.1:9199}"

# Budgets. SPEC §13 expects a 2-4 s Python cold start on Cloud Run, which adds image pull
# and instance scheduling to what is timed here.
COLD_START_MS="${COLD_START_MS:-4000}"     # docker run -> /healthz 200
FIRST_REQUEST_MS="${FIRST_REQUEST_MS:-1500}" # first signed-in request on a fresh instance
PEAK_MEMORY_MIB="${PEAK_MEMORY_MIB:-256}"  # half of Cloud Run's 512 MiB limit
mkdir -p "$OUT"

if [[ "$(uname -s)" == "Linux" ]]; then
  net=(--network host); port=8080
  in_container() { echo "$1"; }
else
  port="${SMOKE_PORT:-18081}"; net=(-p "127.0.0.1:${port}:8080")
  in_container() { echo "host.docker.internal:${1##*:}"; }
fi
url="http://127.0.0.1:${port}"

sampler=""
# shellcheck disable=SC2317  # runs from the EXIT trap
cleanup() {
  status=$?
  if [[ -n "$sampler" ]]; then
    kill "$sampler" 2>/dev/null || true
  fi
  if [[ $status -ne 0 ]]; then
    echo "--- container logs ---"; docker logs "$NAME" 2>&1 | tail -50 || true
  fi
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT

now_ms() { python3 -c 'import time; print(int(time.monotonic() * 1000))'; }

start=$(now_ms)
docker run -d --name "$NAME" "${net[@]}" --read-only --tmpfs /tmp --cpus 1 --memory 512m \
  -e ENV=local -e GCP_PROJECT_ID=demo-activequeue-local -e CONTENT_PROVIDER=fixture \
  -e TRUSTED_PROXY_HOPS=1 -e LOG_LEVEL=WARNING \
  -e FIRESTORE_EMULATOR_HOST="$(in_container "$FIRESTORE")" \
  -e FIREBASE_AUTH_EMULATOR_HOST="$(in_container "$AUTH")" \
  "$IMAGE" >/dev/null
until curl -sf -o /dev/null "$url/healthz"; do
  (( $(now_ms) - start > 60000 )) && { echo "no /healthz 200 within 60 s"; exit 1; }
  sleep 0.05
done
cold=$(( $(now_ms) - start ))

token="$(python3 - "$AUTH" <<'PY'
import sys
sys.path.insert(0, "scripts")
from smoke_test import emulator_id_token
print(emulator_id_token(sys.argv[1], "perf-first-request"))
PY
)"
first_start=$(now_ms)
curl -sf -o /dev/null -H "Authorization: Bearer $token" "$url/api/v1/users/me"
first=$(( $(now_ms) - first_start ))

# Memory every second while k6 runs: docker stats prints e.g. "87.3MiB / 512MiB".
( while true; do docker stats --no-stream --format '{{.MemUsage}}' "$NAME" 2>/dev/null \
    | awk '{print $1}' >> "$OUT/memory.txt"; sleep 1; done ) &
sampler=$!

load_status=0
LOAD_API_URL="$url" "$ROOT/loadtest/run.sh" smoke || load_status=$?
kill "$sampler" 2>/dev/null || true; sampler=""

peak=$(python3 - "$OUT/memory.txt" <<'PY'
import re, sys
units = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024}
peak = 0.0
for line in open(sys.argv[1]):
    m = re.match(r"([\d.]+)(\w+)", line.strip())
    if m:
        peak = max(peak, float(m.group(1)) * units.get(m.group(2), 1))
print(int(peak))
PY
)
oom=$(docker inspect --format '{{.State.OOMKilled}}' "$NAME")

printf '\ncold start %s ms (budget %s), first signed-in request %s ms (budget %s), peak memory %s MiB (budget %s), OOM-killed %s, k6 exit %s\n' \
  "$cold" "$COLD_START_MS" "$first" "$FIRST_REQUEST_MS" "$peak" "$PEAK_MEMORY_MIB" "$oom" "$load_status"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  { echo "### API container performance"; echo
    echo "| Measure | Value | Budget |"; echo "|---|---|---|"
    echo "| Cold start (docker run -> /healthz 200) | ${cold} ms | ${COLD_START_MS} ms |"
    echo "| First signed-in request | ${first} ms | ${FIRST_REQUEST_MS} ms |"
    echo "| Peak memory under the k6 smoke load | ${peak} MiB | ${PEAK_MEMORY_MIB} MiB |"
  } >> "$GITHUB_STEP_SUMMARY"
fi

fail=0
(( cold > COLD_START_MS )) && { echo "::error::cold start ${cold} ms is over ${COLD_START_MS} ms"; fail=1; }
(( first > FIRST_REQUEST_MS )) && { echo "::error::first request ${first} ms is over ${FIRST_REQUEST_MS} ms"; fail=1; }
(( peak > PEAK_MEMORY_MIB )) && { echo "::error::peak memory ${peak} MiB is over ${PEAK_MEMORY_MIB} MiB"; fail=1; }
[[ "$oom" == "true" ]] && { echo "::error::the container was OOM-killed"; fail=1; }
(( load_status != 0 )) && { echo "::error::k6 thresholds failed (exit ${load_status})"; fail=1; }
exit $fail
