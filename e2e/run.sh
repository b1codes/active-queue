#!/usr/bin/env bash
# E2E journeys (ClickUp 86bcxruy6): the real app, built in Release for the simulator,
# against the real FastAPI API and the Firebase Auth + Firestore emulators, with the
# fixture content provider in place of YouTube. See docs/testing.md#e2e-tests.
#
# Run inside the test emulators, as `make e2e` does:
#   firebase emulators:exec --config firebase.test.json ... "e2e/run.sh [flow.yaml ...]"
#
# Needs: the E2E build (frontend/scripts/ios-sim-build.sh e2e), uv, Xcode's simctl, and
# Maestro ($MAESTRO, else `maestro` on PATH). Every run starts from empty emulators and a
# new simulator. Results: frontend/build/e2e/ (report.xml, per-flow screenshots and
# hierarchies, api.log).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${E2E_OUT:-$ROOT/frontend/build/e2e}"
APP="${E2E_APP:-$ROOT/frontend/build/ios/e2e/ActiveQueue.app}"
PORT="${E2E_API_PORT:-8090}"   # must match the build (ios-sim-build.sh e2e)
DEVICE="${E2E_DEVICE:-iPhone 17 Pro}"
RUNTIME="${E2E_RUNTIME:-iOS 26.5}"
MAESTRO="${MAESTRO:-maestro}"
BUNDLE_ID="com.b1codes.activequeue"
export MAESTRO_CLI_NO_ANALYTICS=1 MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true

: "${FIRESTORE_EMULATOR_HOST:?run inside firebase emulators:exec (see make e2e)}"
: "${FIREBASE_AUTH_EMULATOR_HOST:?run inside firebase emulators:exec}"
[[ -d "$APP" ]] || { echo "e2e: no build at $APP; run frontend/scripts/ios-sim-build.sh e2e" >&2; exit 1; }
project="${GCLOUD_PROJECT:-demo-activequeue-local}"
rm -rf "$OUT"
mkdir -p "$OUT"

api_pid=""
udid=""
# shellcheck disable=SC2317  # runs from the EXIT trap
cleanup() {
  if [[ -n "$api_pid" ]]; then
    kill "$api_pid" 2>/dev/null || true
  fi
  if [[ -n "$udid" ]]; then
    xcrun simctl shutdown "$udid" 2>/dev/null || true
    xcrun simctl delete "$udid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# Empty emulators, so no journey sees data it didn't create.
curl -sf -X DELETE "http://$FIRESTORE_EMULATOR_HOST/emulator/v1/projects/$project/databases/(default)/documents" >/dev/null
curl -sf -X DELETE "http://$FIREBASE_AUTH_EMULATOR_HOST/emulator/v1/projects/$project/accounts" >/dev/null

# FIXTURE_PAGE_LATENCY_MS: a Data API page takes 100-300 ms; without it a 1,200-item sync
# ends before the progress bar can be seen.
(cd "$ROOT/backend" && ENV=local CONTENT_PROVIDER=fixture FIXTURE_PAGE_LATENCY_MS=200 GCLOUD_PROJECT="$project" \
  exec uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port "$PORT") > "$OUT/api.log" 2>&1 &
api_pid=$!
for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break
  sleep 1
done
curl -sf "http://127.0.0.1:$PORT/health" >/dev/null || { cat "$OUT/api.log"; exit 1; }

# A new simulator, so no setting, keyboard or app data carries over.
runtime_id=$(xcrun simctl list runtimes -j | python3 -c "
import json, sys
rs = [r for r in json.load(sys.stdin)['runtimes'] if r['isAvailable'] and r['name'] == sys.argv[1]]
print(rs[0]['identifier'] if rs else '')" "$RUNTIME")
[[ -n "$runtime_id" ]] || { echo "e2e: runtime $RUNTIME isn't installed" >&2; exit 1; }
for old in $(xcrun simctl list devices -j | python3 -c "
import json, sys
print(' '.join(d['udid'] for ds in json.load(sys.stdin)['devices'].values() for d in ds if d['name'] == 'aq-e2e'))"); do
  xcrun simctl shutdown "$old" 2>/dev/null || true
  xcrun simctl delete "$old"
done
udid=$(xcrun simctl create aq-e2e "$DEVICE" "$runtime_id")
# The keyboard: English only, no autocorrect, predictions or swipe-typing intro. XCTest
# types key by key, and those rewrite or swallow keys (a host with a Pinyin input source
# hands it to every new simulator).
prefs() { xcrun simctl spawn "$udid" defaults write "$@"; }
xcrun simctl boot "$udid"
xcrun simctl bootstatus "$udid" -b >/dev/null
prefs -g AppleLanguages -array en
prefs -g AppleLocale -string en_US
prefs -g AppleKeyboards -array "en_US@sw=QWERTY;hw=Automatic"
for key in KeyboardAutocorrection KeyboardPrediction KeyboardAutocapitalization \
  KeyboardCheckSpelling KeyboardContinuousPathEnabled; do
  prefs com.apple.Preferences "$key" -bool false
done
prefs com.apple.Preferences DidShowContinuousPathIntroduction -bool true
prefs com.apple.keyboard.preferences DidShowContinuousPathIntroduction -bool true
xcrun simctl shutdown "$udid"
xcrun simctl boot "$udid"
xcrun simctl bootstatus "$udid" -b >/dev/null
xcrun simctl install "$udid" "$APP"
echo "e2e: $DEVICE, $RUNTIME ($udid); API on :$PORT"

flows=("$@")
[[ ${#flows[@]} -gt 0 ]] || flows=("$ROOT/e2e/flows")
status=0
"$MAESTRO" --device "$udid" test "${flows[@]}" \
  --format junit --output "$OUT/report.xml" --test-output-dir "$OUT/artifacts" \
  -e PASSWORD=e2e-password-1 -e "AUTH_EMULATOR=http://$FIREBASE_AUTH_EMULATOR_HOST" || status=$?

# Server-side: no journey may have caused a 5xx.
if grep -qE 'status_code=5[0-9]{2}' <(sed 's/\x1b\[[0-9;]*m//g' "$OUT/api.log"); then
  echo "e2e: the API answered a journey with a 5xx (see $OUT/api.log)" >&2
  status=1
fi
xcrun simctl terminate "$udid" "$BUNDLE_ID" 2>/dev/null || true
exit "$status"
