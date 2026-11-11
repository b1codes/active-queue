#!/usr/bin/env bash
# Takes the screenshots a CI run captured as the new baselines (ClickUp 86bcxruz4).
#
#   scripts/screenshots/accept.sh <run-id>      (make screenshots RUN=<run-id>)
#
# CI's screenshots job is the reference platform, so a baseline change is reviewed there:
# when the job fails, its "screenshots" artifact holds actual/, diff/ and report.json.
# Look at the diffs, then accept the run here and commit the result. Needs the gh CLI.
set -euo pipefail

run="${1:?usage: $0 <ci-run-id>}"
cd "$(dirname "$0")/../.."
dest="build/screenshots-ci/$run"
rm -rf "$dest"
gh run download "$run" --name screenshots --dir "$dest"

for tier in tier1 tier3; do
  [[ -d "$dest/actual/$tier" ]] || { echo "accept: run $run has no actual/$tier" >&2; exit 1; }
done
if ! python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["onReference"] else 1)' "$dest/report.json"; then
  echo "accept: run $run wasn't on the reference platform (report.json onReference=false)" >&2
  exit 1
fi

for tier in tier1 tier3; do
  # Replace the whole tier, so baselines of removed stories go too.
  rm -rf "screenshots/baselines/$tier"
  mkdir -p "screenshots/baselines/$tier"
  # Story captures only, not the frames kept from a capture that never settled.
  find "$dest/actual/$tier" -maxdepth 1 -name '*.png' ! -name '*.unsettled-*' \
    -exec cp {} "screenshots/baselines/$tier/" \;
done
git status --short screenshots/baselines
echo "accept: baselines now match run $run. Review with 'git diff --stat' and commit."
