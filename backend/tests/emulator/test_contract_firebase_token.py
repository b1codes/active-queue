"""ID tokens minted by the Firebase Auth emulator satisfy the claims contract.

contracts/third_party/firebase/id_token_claims.schema.json lists the claims the backend
depends on. The emulator mints tokens with production's claim layout (it skips only the
signature), so this checks the schema against real Firebase output on every PR. The
nightly job checks the production signing certificates.
"""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any

from tests.contract.test_third_party_recorded import errors_for

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.emulator.conftest import EmulatorUser


def _payload(token: str) -> dict[str, Any]:
    segment = token.split(".")[1]
    claims: dict[str, Any] = json.loads(
        base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    )
    return claims


def test_emulator_password_token_satisfies_claims_contract(
    make_user: Callable[..., EmulatorUser],
) -> None:
    user = make_user("claims@example.com", "Claims Contract")
    claims = _payload(user.id_token)
    errors = errors_for("firebase/id_token_claims", claims)
    assert not errors, "\n".join(errors)
    assert claims["sub"] == claims["user_id"] == user.uid
    assert claims["firebase"]["sign_in_provider"] == "password"
    assert claims["email"] == "claims@example.com"
