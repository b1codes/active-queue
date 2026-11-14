"""Live third-party contract checks: real network, real quota. Nightly only.

Skipped unless LIVE_CONTRACTS=1 (set by .github/workflows/contracts-nightly.yml). They
check that the real YouTube Data API and Firebase Auth still match contracts/third_party/,
the same schemas the recorded fixtures are held to on every PR.
"""

from __future__ import annotations

import os

import pytest

LIVE = os.environ.get("LIVE_CONTRACTS") == "1"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    here = os.path.dirname(__file__)
    for item in items:
        if str(item.fspath).startswith(here):
            item.add_marker(pytest.mark.live)
            if not LIVE:
                item.add_marker(pytest.mark.skip(reason="live check; set LIVE_CONTRACTS=1"))


def require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        pytest.fail(f"LIVE_CONTRACTS=1 but {name} is not set")
    return value
