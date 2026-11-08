"""scripts/deploy.sh control flow, with gcloud, gh, firebase, terraform and python3 stubbed.

The deploy script can't run against GCP in CI, but its decisions can be tested:
- which image it deploys
- that it applies only a reviewed plan
- that it refuses unsafe states before changing anything
- that it rolls back when the smoke check fails

Run with `python3 -m unittest discover -s scripts/tests` (stdlib only).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIGEST = "sha256:" + "ab" * 32

# One stub for every tool. It logs its argv and answers from environment knobs.
STUB = (
    textwrap.dedent(
        r"""
    #!/usr/bin/env bash
    tool="$(basename "$0")"
    echo "$tool $*" >> "$STUB_LOG"
    args=" $* "
    case "$tool" in
      gh) echo "${GH_CI_SUCCESSES:-1}" ;;
      firebase) exit 0 ;;
      python3) exit "${SMOKE_EXIT:-0}" ;;
      terraform)
        if [[ "$args" == *" output -raw cloud_run_url "* ]]; then echo "https://api.example.test"; fi
        exit 0 ;;
      gcloud)
        case "$args" in
          *" secrets versions access "*) echo "secret-from-secret-manager" ;;
          *" secrets describe "*) exit 0 ;;
          *" secrets versions list "*) [[ -n "${NO_YOUTUBE_VERSION:-}" ]] || echo "versions/1" ;;
          *" iam service-accounts describe "*) [[ -z "${FIRST_DEPLOY:-}" ]] || exit 1 ;;
          *" iam service-accounts sign-jwt "*) exit "${SIGN_EXIT:-0}" ;;
          *" artifacts repositories describe "*) [[ -z "${FIRST_DEPLOY:-}" ]] || exit 1 ;;
          *" builds submit "*) exit 0 ;;
          *" artifacts docker images describe "*) echo "__DIGEST__" ;;
          *" run services describe "*) [[ -n "${FIRST_DEPLOY:-}" ]] || echo "activequeue-api-dev-00007-old" ;;
          *" run services update-traffic "*) exit 0 ;;
          *) echo "unexpected gcloud call: $*" >&2; exit 99 ;;
        esac ;;
    esac
    """
    )
    .lstrip()
    .replace("__DIGEST__", DIGEST)
)


class DeployScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = self.tmp / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        (self.repo / "backend").mkdir()
        (self.repo / "infra/environments/dev").mkdir(parents=True)
        shutil.copy(REPO / "scripts/deploy.sh", self.repo / "scripts/deploy.sh")
        (self.repo / "backend/Dockerfile").write_text("FROM scratch\n")
        self._git("init", "-q")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "fixture")

        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for tool in ("gh", "gcloud", "firebase", "terraform", "python3"):
            path = self.bin / tool
            path.write_text(STUB)
            path.chmod(0o755)
        self.log = self.tmp / "calls.log"
        self.log.touch()

    def _git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            cwd=self.repo,
            check=True,
        )

    def deploy(self, stdin: str = "dev\n", **knobs: str) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.tmp),
            "STUB_LOG": str(self.log),
            "FIREBASE_WEB_API_KEY": "web-api-key",
            "TF_VAR_google_oauth_client_id": "client.apps.googleusercontent.com",
            **knobs,
        }
        return subprocess.run(
            ["bash", "scripts/deploy.sh", "dev"],
            cwd=self.repo,
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def calls(self, tool: str | None = None) -> list[str]:
        lines = self.log.read_text().splitlines()
        return [line for line in lines if tool is None or line.startswith(f"{tool} ")]

    # --- The happy path -----------------------------------------------------------------

    def test_deploys_the_built_digest_through_a_reviewed_plan(self) -> None:
        result = self.deploy()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, capture_output=True, text=True
        ).stdout.strip()
        registry = "us-central1-docker.pkg.dev/activequeue-dev/activequeue-api-dev"
        build = next(c for c in self.calls("gcloud") if " builds submit " in f" {c} ")
        self.assertIn(f"--tag {registry}/api:{sha}", build)

        tf = self.calls("terraform")
        plan = next(c for c in tf if " plan " in f" {c} ")
        self.assertIn(f"container_image={registry}/api@{DIGEST}", plan)
        self.assertIn("-out=", plan)
        apply = next(c for c in tf if " apply " in f" {c} ")
        self.assertTrue(apply.rstrip().endswith("deploy.tfplan"), apply)
        self.assertNotIn("auto-approve", self.log.read_text())
        self.assertNotIn(":latest", self.log.read_text())

        smoke = self.calls("python3")
        self.assertEqual(len(smoke), 1)
        for flag in (
            "--expect-verified-tokens",
            "--auth custom-token",
            "https://api.example.test",
        ):
            self.assertIn(flag, smoke[0])
        self.assertFalse([c for c in self.calls("gcloud") if "update-traffic" in c])

    def test_firestore_rules_and_indexes_deploy_before_the_new_revision(self) -> None:
        self.assertEqual(self.deploy().returncode, 0)
        order = self.calls()
        firebase = next(i for i, c in enumerate(order) if c.startswith("firebase deploy"))
        apply = next(
            i for i, c in enumerate(order) if c.startswith("terraform") and " apply " in c
        )
        self.assertLess(firebase, apply)

    def test_reads_oauth_secrets_from_secret_manager_when_unset(self) -> None:
        self.assertEqual(self.deploy().returncode, 0)
        accessed = [c for c in self.calls("gcloud") if "secrets versions access" in c]
        self.assertTrue(any("google-oauth-client-secret-dev" in c for c in accessed))
        self.assertTrue(any("apple-oauth-client-secret-dev" in c for c in accessed))

    # --- Rollback -----------------------------------------------------------------------

    def test_failed_smoke_check_rolls_traffic_back_to_the_previous_revision(self) -> None:
        result = self.deploy(SMOKE_EXIT="1")
        self.assertEqual(result.returncode, 1)
        rollback = [c for c in self.calls("gcloud") if "update-traffic" in c]
        self.assertEqual(len(rollback), 1, self.calls("gcloud"))
        self.assertIn("--to-revisions activequeue-api-dev-00007-old=100", rollback[0])

    # --- Refusals before anything changes -----------------------------------------------

    def assert_changed_nothing(self) -> None:
        log = self.log.read_text()
        for mutation in ("builds submit", "firebase deploy", " apply ", "update-traffic"):
            self.assertNotIn(mutation, log)

    def test_not_confirming_the_plan_applies_nothing(self) -> None:
        result = self.deploy(stdin="no\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not confirmed", result.stderr)
        self.assertFalse([c for c in self.calls("terraform") if " apply " in f" {c} "])
        self.assertFalse(self.calls("python3"))

    def test_refuses_a_dirty_working_tree(self) -> None:
        (self.repo / "backend/Dockerfile").write_text("FROM scratch\n# edited\n")
        result = self.deploy()
        self.assertEqual(result.returncode, 1)
        self.assertIn("uncommitted changes", result.stderr)
        self.assert_changed_nothing()

    def test_refuses_a_commit_ci_has_not_passed(self) -> None:
        result = self.deploy(GH_CI_SUCCESSES="0")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no successful CI run", result.stderr)
        self.assert_changed_nothing()

    def test_refuses_when_the_smoke_token_cannot_be_signed(self) -> None:
        result = self.deploy(SIGN_EXIT="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("can't sign JWTs", result.stderr)
        self.assert_changed_nothing()

    def test_refuses_when_the_youtube_secret_has_no_version(self) -> None:
        result = self.deploy(NO_YOUTUBE_VERSION="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("youtube-api-key-dev has no enabled version", result.stderr)
        self.assert_changed_nothing()

    def test_refuses_without_the_smoke_check_inputs(self) -> None:
        result = self.deploy(FIREBASE_WEB_API_KEY="")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FIREBASE_WEB_API_KEY", result.stderr)
        self.assert_changed_nothing()

    def test_rejects_an_unknown_environment(self) -> None:
        result = subprocess.run(
            ["bash", "scripts/deploy.sh", "qa"], cwd=self.repo, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Usage", result.stderr)

    # --- First deploy -------------------------------------------------------------------

    def test_first_deploy_creates_the_registry_then_deploys_without_rollback_target(self) -> None:
        result = self.deploy(stdin="dev\ndev\n", FIRST_DEPLOY="1", SMOKE_EXIT="1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        plans = [c for c in self.calls("terraform") if " plan " in f" {c} "]
        self.assertEqual(len(plans), 2)
        self.assertIn(
            "-target module.dev_app.google_artifact_registry_repository.api_repo", plans[0]
        )
        self.assertNotIn("-target", plans[1])
        self.assertIn("no revision to roll back to", result.stderr)
        self.assertFalse([c for c in self.calls("gcloud") if "update-traffic" in c])


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    unittest.main()
