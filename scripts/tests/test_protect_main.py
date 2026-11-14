"""The main-branch ruleset, its required check, and scripts/protect-main.sh.

A required check that never reports blocks every pull request. These tests keep the
ruleset's required context tied to the `CI Passed` job in ci.yml, and keep that job a
real gate: it runs on every PR, is never skipped, and waits on every other job. The apply
script runs against a stubbed `gh`. Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RULESET = REPO / ".github/rulesets/main.json"
CI = REPO / ".github/workflows/ci.yml"
GITHUB_ACTIONS_APP_ID = 15368


def ci_jobs() -> dict[str, str]:
    """Each top-level job in ci.yml, mapped to the text of its definition."""
    text = CI.read_text()
    body = text[text.index("\njobs:\n") + len("\njobs:\n") :]
    parts = re.split(r"^  ([a-z][a-z0-9_-]*):\n", body, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2], strict=True))


class RulesetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ruleset = json.loads(RULESET.read_text())
        self.rules = {rule["type"]: rule.get("parameters", {}) for rule in self.ruleset["rules"]}

    def test_protects_the_default_branch_with_no_bypass(self) -> None:
        self.assertEqual(self.ruleset["target"], "branch")
        self.assertEqual(self.ruleset["enforcement"], "active")
        self.assertEqual(self.ruleset["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        self.assertEqual(self.ruleset["bypass_actors"], [])
        for rule in ("deletion", "non_fast_forward", "pull_request", "required_status_checks"):
            self.assertIn(rule, self.rules)

    def test_requires_only_ci_passed_from_github_actions(self) -> None:
        checks = self.rules["required_status_checks"]["required_status_checks"]
        self.assertEqual(
            checks, [{"context": "CI Passed", "integration_id": GITHUB_ACTIONS_APP_ID}]
        )

    def test_the_required_context_is_the_ci_passed_job(self) -> None:
        context = self.rules["required_status_checks"]["required_status_checks"][0]["context"]
        job = ci_jobs()["ci-passed"]
        self.assertRegex(job, rf"(?m)^    name: {re.escape(context)}$")

    def test_ci_passed_always_runs_and_waits_on_every_other_job(self) -> None:
        jobs = ci_jobs()
        gate = jobs.pop("ci-passed")
        self.assertRegex(gate, r"(?m)^    if: always\(\)$")
        needs = re.search(r"(?m)^    needs: \[(.*)\]$", gate)
        self.assertIsNotNone(needs, "ci-passed needs must be a one-line list")
        assert needs is not None
        listed = {name.strip() for name in needs.group(1).split(",")}
        self.assertEqual(listed, set(jobs), "add every CI job to ci-passed's needs")
        for name, job in jobs.items():
            self.assertNotRegex(
                job, r"(?m)^    if:", f"{name} can be skipped, which fails CI Passed"
            )
        for result in ("failure", "cancelled", "skipped"):
            self.assertIn(result, gate)

    def test_ci_runs_on_every_pull_request_to_main(self) -> None:
        trigger = CI.read_text().split("\njobs:\n")[0]
        self.assertRegex(trigger, r"(?m)^  pull_request:\n    branches: \[main\]$")
        self.assertNotIn("paths", trigger)


STUB = textwrap.dedent(
    r"""
    #!/usr/bin/env bash
    echo "gh $*" >> "$STUB_LOG"
    case " $* " in
      *" repo view "*) echo "owner/repo" ;;
      *" --method "*) cat > /dev/null; echo "applied" ;;
      *" repos/owner/repo/rulesets/"*) cat "$LIVE_RULESET" ;;
      *" repos/owner/repo/rulesets "*) [[ -z "${EXISTING_ID:-}" ]] || echo "$EXISTING_ID" ;;
      *) echo "unexpected gh call: $*" >&2; exit 99 ;;
    esac
    """
).lstrip()


class ProtectMainScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = self.tmp / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        (self.repo / ".github/rulesets").mkdir(parents=True)
        shutil.copy(REPO / "scripts/protect-main.sh", self.repo / "scripts/protect-main.sh")
        shutil.copy(RULESET, self.repo / ".github/rulesets/main.json")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(STUB)
        (bin_dir / "gh").chmod(0o755)
        self.log = self.tmp / "calls.log"
        self.log.touch()
        self.live = self.tmp / "live.json"
        # What GitHub returns: the file's fields plus server-side ones, rules in any order.
        live = json.loads(RULESET.read_text())
        live.update(id=7, source="owner/repo", source_type="Repository", node_id="RRS_x")
        live["rules"].reverse()
        self.live.write_text(json.dumps(live))
        self.env = {
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STUB_LOG": str(self.log),
            "LIVE_RULESET": str(self.live),
        }

    def run_script(self, *args: str, **knobs: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "scripts/protect-main.sh", *args],
            cwd=self.repo,
            env={**self.env, **knobs},
            capture_output=True,
            text=True,
            timeout=30,
        )

    def writes(self) -> list[str]:
        return [line for line in self.log.read_text().splitlines() if "--method" in line]

    def test_creates_the_ruleset_when_none_exists(self) -> None:
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.writes(),
            [
                "gh api --method POST repos/owner/repo/rulesets --input .github/rulesets/main.json"
                ' --jq "Created ruleset \\(.name) (id \\(.id))"'
            ],
        )

    def test_updates_the_existing_ruleset_in_place(self) -> None:
        result = self.run_script(EXISTING_ID="7")
        self.assertEqual(result.returncode, 0, result.stderr)
        writes = self.writes()
        self.assertEqual(len(writes), 1)
        self.assertIn("--method PUT repos/owner/repo/rulesets/7 ", writes[0])

    def test_check_passes_when_live_matches_the_file(self) -> None:
        result = self.run_script("--check", EXISTING_ID="7")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.writes(), [])

    def test_check_fails_when_live_drifts(self) -> None:
        live = json.loads(self.live.read_text())
        live["enforcement"] = "evaluate"
        self.live.write_text(json.dumps(live))
        result = self.run_script("--check", EXISTING_ID="7")
        self.assertEqual(result.returncode, 1)
        self.assertIn("differs", result.stderr)

    def test_check_fails_when_the_ruleset_is_missing(self) -> None:
        result = self.run_script("--check")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.writes(), [])


if __name__ == "__main__":
    unittest.main()
