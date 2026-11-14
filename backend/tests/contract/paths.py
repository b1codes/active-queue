"""Locations of the shared contract files (repo-root `contracts/`)."""

from __future__ import annotations

import os
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"
OPENAPI_PATH = CONTRACTS_DIR / "openapi.json"
INTERACTIONS_DIR = CONTRACTS_DIR / "interactions"
THIRD_PARTY_DIR = CONTRACTS_DIR / "third_party"

# `UPDATE_CONTRACTS=1 pytest tests/contract` (or `make contracts`) rewrites generated files.
UPDATE = os.environ.get("UPDATE_CONTRACTS") == "1"
