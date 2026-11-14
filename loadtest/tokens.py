#!/usr/bin/env python3
"""Mint ID tokens for the load test's users and write them as JSON for k6 (ClickUp 86bcxrv0j).

  --auth emulator       unsigned custom tokens, exchanged with the Auth emulator
  --auth custom-token   custom tokens signed by --signer via gcloud, exchanged with
                        Identity Toolkit (staging); same requirements as smoke_test.py

Each user is a fixed uid (`<prefix>-<n>`), so reruns reuse the same accounts.
Standard library only, like scripts/smoke_test.py, whose sign-in code this reuses.
"""

# ruff: noqa: T201 - a CLI

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from smoke_test import emulator_id_token, signed_id_token


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--users", type=int, required=True)
    parser.add_argument("--uid-prefix", default="load-user")
    parser.add_argument("--auth", choices=["emulator", "custom-token"], default="emulator")
    parser.add_argument("--auth-emulator-host", default="127.0.0.1:9199")
    parser.add_argument("--signer", help="service account that signs custom tokens")
    parser.add_argument("--firebase-api-key", help="the project's Web API key")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    tokens = []
    for n in range(args.users):
        uid = f"{args.uid_prefix}-{n}"
        if args.auth == "emulator":
            tokens.append(emulator_id_token(args.auth_emulator_host, uid))
        else:
            if not (args.signer and args.firebase_api_key):
                parser.error("--auth custom-token needs --signer and --firebase-api-key")
            tokens.append(signed_id_token(args.signer, args.firebase_api_key, uid))
    args.out.write_text(json.dumps(tokens))
    print(f"wrote {len(tokens)} ID tokens to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
