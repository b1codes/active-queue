"""scripts/smoke_test.py against a fake API, one broken behavior at a time.

`make test-container` and the CI container job run the smoke check against the real
image. These tests prove it fails for each fault it exists to catch. Stdlib only.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import socketserver
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

_SPEC = importlib.util.spec_from_file_location(
    "smoke_test", Path(__file__).resolve().parents[1] / "smoke_test.py"
)
assert _SPEC and _SPEC.loader
smoke_test = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(smoke_test)

GOOD_TOKEN = "id-token-from-identity-toolkit"


class FakeApi(BaseHTTPRequestHandler):
    """Behaves like a healthy deployment unless a fault is switched on."""

    faults: ClassVar[set[str]] = set()

    def log_message(self, *args: Any) -> None:
        pass

    def _send(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _ok(self, data: Any) -> None:
        self._send(200, {"status": "success", "data": data, "error": None})

    def do_POST(self) -> None:
        if self.path.startswith(
            "/identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"
        ):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            claims = json.loads(
                smoke_test.base64.urlsafe_b64decode(body["token"].split(".")[1] + "==")
            )
            self.server.uid = claims["uid"]  # type: ignore[attr-defined]
            self._send(200, {"idToken": GOOD_TOKEN})
            return
        self._send(404, {})

    def do_GET(self) -> None:
        auth = self.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ") if auth.startswith("Bearer ") else None
        if self.path == "/health":
            if "health-reserved" in self.faults:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Google 404")
                return
            fs = "down" if "firestore-down" in self.faults else "up"
            self._ok({"status": "healthy", "firestore": {"status": fs, "latency_ms": 1}})
            return
        authorized = token == GOOD_TOKEN or (token and "accepts-forged" in self.faults)
        if not authorized and "no-auth" not in self.faults:
            self._send(401, {"status": "error", "error": {"code": "AUTH_TOKEN_MISSING"}})
            return
        if self.path == "/api/v1/users/me":
            uid = "someone-else" if "wrong-user" in self.faults else self.server.uid  # type: ignore[attr-defined]
            self._ok({"user": {"uid": uid}})
        elif self.path == "/api/v1/activities":
            self._ok({"activities": [] if "empty-catalog" in self.faults else [{"id": "running"}]})
        else:
            self._send(404, {})


class _Server(ThreadingHTTPServer):
    def server_bind(self) -> None:
        # HTTPServer.server_bind does a reverse DNS lookup (socket.getfqdn), which can
        # stall for tens of seconds on a machine with slow DNS. The name isn't needed.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]


class SmokeTestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = _Server(("127.0.0.1", 0), FakeApi)
        cls.server.uid = None  # type: ignore[attr-defined]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.host = f"127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def run_smoke(self, *faults: str, verified: bool = True) -> tuple[int, str]:
        FakeApi.faults = set(faults)
        argv = [f"http://{self.host}", "--auth", "emulator", "--auth-emulator-host", self.host]
        argv += ["--wait", "0", "--uid", "smoke-test-unit"]
        if verified:
            argv += ["--expect-verified-tokens", "--project", "demo-smoke"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = smoke_test.run(smoke_test.parse_args(argv))
        return code, out.getvalue()

    def test_a_healthy_deployment_passes(self) -> None:
        code, out = self.run_smoke()
        self.assertEqual(code, 0, out)
        self.assertIn("smoke test passed", out)
        self.assertEqual(out.count("ok    "), 6, out)

    def assert_fails(self, fault: str, check: str) -> None:
        code, out = self.run_smoke(fault)
        self.assertEqual(code, 1, out)
        failed = [line for line in out.splitlines() if line.startswith("FAIL")]
        self.assertTrue(any(check in line for line in failed), out)

    def test_fails_when_health_is_unreachable(self) -> None:
        self.assert_fails("health-reserved", "GET /health")

    def test_fails_when_firestore_is_down(self) -> None:
        self.assert_fails("firestore-down", "GET /health")

    def test_fails_when_auth_is_not_enforced(self) -> None:
        self.assert_fails("no-auth", "without a token is 401")

    def test_fails_when_forged_tokens_are_accepted(self) -> None:
        self.assert_fails("accepts-forged", "forged token is 401")

    def test_forged_token_check_is_opt_in(self) -> None:
        code, out = self.run_smoke("accepts-forged", verified=False)
        self.assertEqual(code, 0, out)
        self.assertNotIn("forged", out)

    def test_fails_when_me_returns_another_user(self) -> None:
        self.assert_fails("wrong-user", "GET /users/me")

    def test_fails_when_the_catalog_is_empty(self) -> None:
        self.assert_fails("empty-catalog", "GET /activities")

    def test_forged_token_has_valid_claims_and_a_bogus_signature(self) -> None:
        token = smoke_test.forged_id_token("demo-smoke", "u1")
        header, claims, signature = token.split(".")
        claims_json = json.loads(smoke_test.base64.urlsafe_b64decode(claims + "=="))
        self.assertEqual(claims_json["aud"], "demo-smoke")
        self.assertEqual(claims_json["iss"], "https://securetoken.google.com/demo-smoke")
        self.assertEqual(claims_json["sub"], "u1")
        self.assertGreater(len(signature), 300)
        self.assertIn("RS256", smoke_test.base64.urlsafe_b64decode(header + "==").decode())

    def test_custom_token_mode_requires_a_signer_and_api_key(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            smoke_test.parse_args(["https://x", "--auth", "custom-token"])


if __name__ == "__main__":
    unittest.main()
