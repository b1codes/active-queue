#!/usr/bin/env bash
# Apply .github/rulesets/main.json to this repo's default branch (ClickUp 86bcxruyn, 86bbb7ru0).
#
#   scripts/protect-main.sh           create the ruleset, or update it in place
#   scripts/protect-main.sh --check   exit 1 if the live ruleset differs from the file
#
# The ruleset: changes reach main only through a pull request whose `CI Passed` check (from
# GitHub Actions) succeeded; main can't be force-pushed or deleted; nobody bypasses it.
# Needs `gh` signed in as a repo admin. Run it again after editing the JSON.
set -euo pipefail

cd "$(dirname "$0")/.."

RULESET_FILE=".github/rulesets/main.json"
MODE="${1:-apply}"
if [[ "$MODE" != "apply" && "$MODE" != "--check" ]]; then
  echo "Usage: $0 [--check]" >&2
  exit 2
fi

REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
NAME="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$RULESET_FILE")"
ID="$(gh api "repos/${REPO}/rulesets" --jq ".[] | select(.name == \"${NAME}\") | .id")"

# The fields this file sets, from a ruleset GitHub returns, in a comparable form.
normalize() {
  python3 -c '
import json, sys
r = json.load(sys.stdin)
keep = {k: r.get(k) for k in ("name", "target", "enforcement", "conditions", "bypass_actors")}
keep["rules"] = sorted(r.get("rules", []), key=lambda rule: rule["type"])
print(json.dumps(keep, sort_keys=True))
'
}

if [[ "$MODE" == "--check" ]]; then
  if [[ -z "$ID" ]]; then
    echo "No ruleset named '${NAME}' on ${REPO}. Run scripts/protect-main.sh." >&2
    exit 1
  fi
  want="$(normalize < "$RULESET_FILE")"
  have="$(gh api "repos/${REPO}/rulesets/${ID}" | normalize)"
  if [[ "$want" != "$have" ]]; then
    echo "Ruleset '${NAME}' (id ${ID}) on ${REPO} differs from ${RULESET_FILE}." >&2
    echo "want: ${want}" >&2
    echo "have: ${have}" >&2
    exit 1
  fi
  echo "Ruleset '${NAME}' (id ${ID}) on ${REPO} matches ${RULESET_FILE}."
  exit 0
fi

if [[ -z "$ID" ]]; then
  gh api --method POST "repos/${REPO}/rulesets" --input "$RULESET_FILE" --jq '"Created ruleset \(.name) (id \(.id))"'
else
  gh api --method PUT "repos/${REPO}/rulesets/${ID}" --input "$RULESET_FILE" --jq '"Updated ruleset \(.name) (id \(.id))"'
fi
