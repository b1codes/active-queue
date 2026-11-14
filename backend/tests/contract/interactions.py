"""Shared machinery for the `contracts/` suite: loading, strict schemas, and matching.

An interaction is one request/response pair, written once in `contracts/interactions/`
and checked from both sides:

* provider (tests/emulator/test_contract_provider.py): the request is replayed against
  the real app on the Firestore + Auth emulators. The response must validate against
  the strict OpenAPI schema and equal the recorded example, except at `dynamic` paths.
* consumer (frontend/src/__tests__/contracts/): the app makes exactly this request and
  handles exactly this response.

Placeholders such as `uid_alice`, `src_1` and `sess_1` stand in for values the provider
generates. A provider state returns *bindings* (placeholder -> real value). Requests are
rewritten placeholder -> real before replay, and responses real -> placeholder before
comparison, so examples stay readable and stable.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from tests.contract.paths import INTERACTIONS_DIR, OPENAPI_PATH

AUTH_MODES = frozenset({"alice", "none", "invalid", "expired"})
CANONICAL_TIMESTAMP = "2026-01-01T00:00:00Z"
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


@dataclass
class Interaction:
    file: str
    raw: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.raw["id"])

    @property
    def states(self) -> list[str]:
        return list(self.raw.get("states", []))

    @property
    def method(self) -> str:
        return str(self.raw["request"]["method"])

    @property
    def path(self) -> str:
        return str(self.raw["request"]["path"])

    @property
    def auth(self) -> str:
        return str(self.raw["request"].get("auth", "alice"))

    @property
    def request_body(self) -> Any:
        return self.raw["request"].get("body")

    @property
    def has_request_body(self) -> bool:
        return "body" in self.raw["request"]

    @property
    def status(self) -> int:
        return int(self.raw["response"]["status"])

    @property
    def response_body(self) -> Any:
        return self.raw["response"].get("body")

    @property
    def response_headers(self) -> dict[str, str]:
        return dict(self.raw["response"].get("headers", {}))

    @property
    def dynamic(self) -> list[str]:
        return list(self.raw.get("dynamic", []))


@dataclass
class InteractionFile:
    name: str
    raw: dict[str, Any]
    interactions: list[Interaction] = field(default_factory=list)


def load_files() -> list[InteractionFile]:
    files = []
    for path in sorted(INTERACTIONS_DIR.glob("*.json")):
        raw = json.loads(path.read_text())
        f = InteractionFile(name=path.name, raw=raw)
        f.interactions = [Interaction(path.name, it) for it in raw["interactions"]]
        files.append(f)
    return files


def load_interactions() -> list[Interaction]:
    return [it for f in load_files() for it in f.interactions]


def write_file(f: InteractionFile) -> None:
    (INTERACTIONS_DIR / f.name).write_text(json.dumps(f.raw, indent=2, ensure_ascii=False) + "\n")


# --- OpenAPI lookup and strict schemas ---------------------------------------------------


@cache
def openapi() -> dict[str, Any]:
    spec: dict[str, Any] = json.loads(OPENAPI_PATH.read_text())
    return spec


def _template_regex(template: str) -> re.Pattern[str]:
    return re.compile("^" + re.sub(r"\\\{[^/]+?\\\}", "[^/]+", re.escape(template)) + "$")


def operation_for(method: str, path: str) -> tuple[str, dict[str, Any]]:
    """Return (path template, operation) for a concrete request path."""
    bare = path.split("?", 1)[0]
    matches = [
        (template, item[method.lower()])
        for template, item in openapi()["paths"].items()
        if method.lower() in item and _template_regex(template).match(bare)
    ]
    # Prefer literal segments over parameters (/sessions/active over /sessions/{id}).
    matches.sort(key=lambda m: m[0].count("{"))
    if not matches:
        raise LookupError(f"{method} {path} matches no operation in contracts/openapi.json")
    return matches[0]


def _strictify(node: Any) -> Any:
    """Reject undeclared properties everywhere: a response must not grow silent extras."""
    if isinstance(node, dict):
        out = {k: _strictify(v) for k, v in node.items()}
        if out.get("type") == "object" and "properties" in out:
            out.setdefault("additionalProperties", False)
        return out
    if isinstance(node, list):
        return [_strictify(v) for v in node]
    return node


@cache
def _components() -> dict[str, Any]:
    strict: dict[str, Any] = _strictify(copy.deepcopy(openapi()["components"]))
    return strict


def response_validator(method: str, path: str, status: int) -> Draft202012Validator:
    template, op = operation_for(method, path)
    responses = op["responses"]
    if str(status) not in responses:
        raise LookupError(f"{method} {template} does not document a {status} response")
    schema = responses[str(status)]["content"]["application/json"]["schema"]
    return Draft202012Validator(
        {**schema, "components": _components()}, format_checker=FormatChecker()
    )


def schema_errors(method: str, path: str, status: int, body: Any) -> list[str]:
    validator = response_validator(method, path, status)
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(body), key=lambda e: list(e.absolute_path))
    ]


# --- Bindings and comparison -------------------------------------------------------------


def substitute(value: Any, mapping: dict[str, str]) -> Any:
    """Replace every occurrence of each mapping key inside string values (longest first)."""
    if isinstance(value, str):
        for old in sorted(mapping, key=len, reverse=True):
            value = value.replace(old, mapping[old])
        return value
    if isinstance(value, dict):
        return {k: substitute(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, mapping) for v in value]
    return value


def _dynamic_regex(patterns: list[str]) -> re.Pattern[str] | None:
    if not patterns:
        return None
    parts = [re.escape(p).replace(r"\[\*\]", r"\[\d+\]") for p in patterns]
    return re.compile("^(?:" + "|".join(parts) + ")$")


def _join(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}" if path else key


def mismatches(expected: Any, actual: Any, dynamic: list[str], path: str = "") -> list[str]:
    """Differences between an example and a real body, ignoring values at dynamic paths."""
    dyn = _dynamic_regex(dynamic)
    out: list[str] = []

    def walk(exp: Any, act: Any, at: str) -> None:
        if dyn and at and dyn.match(at):
            return
        if isinstance(exp, dict) and isinstance(act, dict):
            for key in sorted(exp.keys() | act.keys()):
                if key not in act:
                    out.append(f"{_join(at, key)}: missing from response")
                elif key not in exp:
                    out.append(f"{_join(at, key)}: not in the contract example")
                else:
                    walk(exp[key], act[key], _join(at, key))
        elif isinstance(exp, list) and isinstance(act, list):
            if len(exp) != len(act):
                out.append(f"{at or '<root>'}: expected {len(exp)} items, got {len(act)}")
            for idx, (e, a) in enumerate(zip(exp, act, strict=False)):
                walk(e, a, _join(at, idx))
        elif exp != act or type(exp) is not type(act):
            out.append(f"{at or '<root>'}: expected {exp!r}, got {act!r}")

    walk(expected, actual, path)
    return out


def merge_recorded(previous: Any, actual: Any, dynamic: list[str], path: str = "") -> Any:
    """Record mode: take the provider's value, but keep the old example at dynamic paths.

    New dynamic values get a canonical placeholder so a re-record never churns the diff.
    """
    dyn = _dynamic_regex(dynamic)

    def walk(prev: Any, act: Any, at: str) -> Any:
        if dyn and at and dyn.match(at):
            if prev is not None and type(prev) is type(act):
                return prev
            if isinstance(act, str) and _ISO.match(act):
                return CANONICAL_TIMESTAMP
            return act
        if isinstance(act, dict):
            p = prev if isinstance(prev, dict) else {}
            return {k: walk(p.get(k), v, _join(at, k)) for k, v in act.items()}
        if isinstance(act, list):
            p = prev if isinstance(prev, list) else []
            return [walk(p[i] if i < len(p) else None, v, _join(at, i)) for i, v in enumerate(act)]
        return act

    return walk(previous, actual, path)
