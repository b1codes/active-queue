"""Property-based fuzzing of the input sanitizers and request models (SPEC §9.5).

Example-based tests pin known payloads; these let Hypothesis search for inputs that break
the invariants every caller relies on. Text strategies are biased toward the characters
the sanitizers care about (angle brackets, scheme prefixes, control characters, dots,
slashes) so the search reaches interesting compositions quickly.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.core.sanitizer import (
    CONTROL_CHAR_RE,
    DANGEROUS_SCHEME_RE,
    HTML_TAG_RE,
    is_valid_document_id,
    sanitize_document_id,
    sanitize_identifier,
    sanitize_string_list,
    sanitize_text,
    sanitize_url,
)
from app.features.content.schemas import CreateSourceRequest
from app.features.users.schemas import UpdatePreferencesRequest
from app.providers.base import PlaylistMetadata, RawContentItem

FUZZ = settings(
    max_examples=400,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

_FRAGMENTS = [
    "<",
    ">",
    "</",
    "/>",
    "<b>",
    "</b>",
    "<script>",
    "</script>",
    "<style>",
    "<iframe ",
    "javascript:",
    "java",
    "script:",
    "data:",
    "vbscript:",
    "file:",
    "http://",
    "https://",
    "//",
    "../",
    "..\\",
    "..",
    ".",
    "/",
    "\\",
    "__",
    ":",
    "\x00",
    "\x07",
    "\x1b",
    "\x7f",
    "\x85",
    "\t",
    "\n",
    " ",
    "[",
    "]",
    "%2e",
    "%00",
    "é",
    "😀",
]

hostile_text = st.lists(
    st.one_of(st.sampled_from(_FRAGMENTS), st.text(max_size=6)), max_size=24
).map("".join)


def _has_control_chars(s: str) -> bool:
    return bool(CONTROL_CHAR_RE.search(s))


# --------------------------------------------------------------------------- text


@FUZZ
@given(text=hostile_text, max_length=st.one_of(st.none(), st.integers(1, 64)))
@example(text="jav<b>ascript:javascript:alert(1)", max_length=None)
@example(text="java<b>script:alert(1)", max_length=None)
@example(text="<scr<script></script>ipt>alert(1)</script>", max_length=None)
def test_sanitize_text_output_is_inert(text: str, max_length: int | None) -> None:
    out = sanitize_text(text, max_length=max_length)

    assert out is not None
    assert not _has_control_chars(out)
    assert not HTML_TAG_RE.search(out), f"tag survived: {out!r}"
    assert not DANGEROUS_SCHEME_RE.search(out), f"scheme survived: {out!r}"
    assert out == out.strip()
    if max_length is not None:
        assert len(out) <= max_length


@FUZZ
@given(text=hostile_text, max_length=st.one_of(st.none(), st.integers(1, 64)))
def test_sanitize_text_is_idempotent(text: str, max_length: int | None) -> None:
    """Re-sanitizing stored data (e.g. on re-sync) must not change it again."""
    once = sanitize_text(text, max_length=max_length)
    assert sanitize_text(once, max_length=max_length) == once


@FUZZ
@given(items=st.lists(hostile_text, max_size=80))
def test_sanitize_string_list_bounds(items: list[str]) -> None:
    out = sanitize_string_list(items, max_item_length=50, max_items=20)
    assert len(out) <= 20
    for item in out:
        assert item
        assert len(item) <= 50
        assert item == sanitize_text(item, max_length=50)


# --------------------------------------------------------------------------- URLs


@FUZZ
@given(url=hostile_text)
@example(url="http://[")
@example(url="https://[::1")
@example(url="java\tscript:alert(1)")
@example(url=" javascript:alert(1)")
def test_sanitize_url_never_raises_and_only_passes_web_urls(url: str) -> None:
    out = sanitize_url(url)
    if out is None:
        return
    assert urlparse(out).scheme.lower() in ("", "http", "https")
    assert not _has_control_chars(out)
    assert len(out) <= 2048


@FUZZ
@given(url=hostile_text)
def test_sanitize_url_is_idempotent(url: str) -> None:
    once = sanitize_url(url)
    if once is not None:
        assert sanitize_url(once) == once


# --------------------------------------------------------------------------- IDs

# Firestore document ID rules: no "/", not "." or "..", not __.*__, at most 1500 bytes.
_FIRESTORE_RESERVED = re.compile(r"^__.*__$")


@FUZZ
@given(identifier=hostile_text)
@example(identifier="..")
@example(identifier="__name__")
@example(identifier="a/b")
@example(identifier="....//")
def test_accepted_document_ids_are_legal_firestore_ids(identifier: str) -> None:
    if not is_valid_document_id(identifier):
        return
    assert "/" not in identifier
    assert identifier not in (".", "..")
    assert not _FIRESTORE_RESERVED.match(identifier)
    assert len(identifier.encode()) <= 1500
    assert not _has_control_chars(identifier)


@FUZZ
@given(identifier=hostile_text)
def test_sanitize_document_id_returns_a_legal_id_or_rejects(identifier: str) -> None:
    try:
        out = sanitize_document_id(identifier)
    except ValueError:
        return
    if out is not None:
        assert is_valid_document_id(out)
        assert len(out) <= 200


@FUZZ
@given(identifier=hostile_text)
def test_sanitize_identifier_strips_traversal(identifier: str) -> None:
    out = sanitize_identifier(identifier)
    if out is None:
        return
    assert "../" not in out
    assert "..\\" not in out
    assert not _has_control_chars(out)
    assert len(out) <= 200


# --------------------------------------------------------------------------- request models

_json_scalars = st.one_of(
    st.none(), st.booleans(), st.integers(-(2**63), 2**63), st.floats(), hostile_text
)
_json = st.recursive(
    _json_scalars,
    lambda children: st.one_of(
        st.lists(children, max_size=5), st.dictionaries(st.text(max_size=8), children, max_size=5)
    ),
    max_leaves=20,
)
_preference_keys = st.sampled_from(
    [
        "preferred_activity_types",
        "preferred_tracker_app",
        "default_time_block_seconds",
        "hide_completed",
        "dark_mode",
        "sync_enabled",
        "notifications_enabled",
        "unknown_field",
    ]
)


@FUZZ
@given(body=st.dictionaries(_preference_keys, _json, max_size=8))
def test_preferences_request_rejects_or_yields_bounded_values(body: dict[str, object]) -> None:
    try:
        req = UpdatePreferencesRequest.model_validate(body)
    except ValidationError:
        return

    if req.default_time_block_seconds is not None:
        assert 300 <= req.default_time_block_seconds <= 86400
    if req.preferred_tracker_app is not None:
        assert 0 < len(req.preferred_tracker_app) <= 50
        assert req.preferred_tracker_app == sanitize_text(req.preferred_tracker_app, 50)
    if req.preferred_activity_types is not None:
        assert len(req.preferred_activity_types) <= 20
        assert all(0 < len(a) <= 50 for a in req.preferred_activity_types)


@FUZZ
@given(url_or_id=hostile_text)
def test_create_source_request_rejects_or_yields_inert_input(url_or_id: str) -> None:
    try:
        req = CreateSourceRequest.model_validate({"url_or_id": url_or_id})
    except ValidationError:
        return
    assert req.url_or_id
    assert not _has_control_chars(req.url_or_id)
    assert not HTML_TAG_RE.search(req.url_or_id)


# --------------------------------------------------------------------------- provider data


@FUZZ
@given(title=hostile_text, url=hostile_text)
@example(title="<script>alert(1)</script>", url="http://[")
@example(title="<b></b>", url="javascript:alert(1)")
def test_provider_metadata_is_sanitized_even_when_nothing_survives(title: str, url: str) -> None:
    """A playlist owner controls these strings; they must never be stored raw."""
    item = RawContentItem(
        external_id="v1",
        title=title,
        duration_seconds=60,
        published_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
        thumbnail_url=url,
        video_url=url,
    )
    meta = PlaylistMetadata(source_id="PL1", title=title, thumbnail_url=url)
    for value in (item.title, meta.title):
        assert value
        assert value == sanitize_text(value, max_length=500)
    for maybe_url in (item.thumbnail_url, item.video_url, meta.thumbnail_url):
        assert maybe_url is None or maybe_url == sanitize_url(maybe_url)


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_sanitize_url_blank_is_none(bad: str | None) -> None:
    assert sanitize_url(bad) is None
