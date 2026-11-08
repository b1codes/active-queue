from __future__ import annotations

import re
from urllib.parse import urlparse

# Pattern matching control characters (ASCII 0-8, 11-12, 14-31, 127, and C1 controls 128-159)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Pattern for stripping script/style/iframe tags and their inner content
SCRIPT_TAG_RE = re.compile(
    r"<(script|style|iframe|applet|embed|object)[^>]*?>.*?</\1>", re.IGNORECASE | re.DOTALL
)

# Pattern for stripping remaining HTML tags to prevent HTML/XSS injection
HTML_TAG_RE = re.compile(r"<[^>]*?>")

# Dangerous URI scheme patterns (e.g. javascript:, data:, vbscript:)
DANGEROUS_SCHEME_RE = re.compile(r"^\s*(javascript|data|vbscript|file):", re.IGNORECASE)

# Path traversal pattern (../, ..\, null bytes)
PATH_TRAVERSAL_RE = re.compile(r"\.\.[/\\]")


def _strip_markup_once(text: str) -> str:
    cleaned = SCRIPT_TAG_RE.sub("", text)
    cleaned = CONTROL_CHAR_RE.sub("", cleaned)
    cleaned = HTML_TAG_RE.sub("", cleaned)
    return DANGEROUS_SCHEME_RE.sub("", cleaned).strip()


def sanitize_text(text: str | None, max_length: int | None = None) -> str | None:
    """Sanitize free text: strip control chars, HTML tags, and leading dangerous schemes.

    The passes repeat until nothing changes. A single pass can be defeated by nesting,
    because removing one construct can assemble another: "jav<b>ascript:javascript:x"
    loses its tag and then one scheme, which leaves "javascript:x". Every pass that
    changes anything makes the string shorter, so the loop terminates. The result is
    idempotent, so re-sanitizing stored data never changes it again.
    """
    if text is None:
        return None

    cleaned = text.strip()
    previous = None
    while cleaned != previous:
        previous = cleaned
        cleaned = _strip_markup_once(cleaned)

    if max_length is not None and len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned.strip()


def sanitize_url(url: str | None, max_length: int = 2048) -> str | None:
    """Validate and sanitize URL input. Only http and https schemes are permitted."""
    if url is None:
        return None

    cleaned = url.strip()
    if not cleaned:
        return None

    # Strip control chars and null bytes
    cleaned = CONTROL_CHAR_RE.sub("", cleaned).strip()
    if not cleaned or len(cleaned) > max_length:
        return None

    # Reject dangerous schemes
    if DANGEROUS_SCHEME_RE.search(cleaned):
        return None

    try:
        parsed = urlparse(cleaned)
    except ValueError:  # e.g. "http://[" (unterminated IPv6 literal)
        return None
    if parsed.scheme and parsed.scheme.lower() not in ("http", "https"):
        return None

    return cleaned


def sanitize_identifier(identifier: str | None, max_length: int = 200) -> str | None:
    """Sanitize ID or path parameter by stripping path traversal, null bytes, and control characters."""
    if identifier is None:
        return None

    cleaned = identifier.strip()
    if not cleaned:
        return None

    # Strip control chars
    cleaned = CONTROL_CHAR_RE.sub("", cleaned)

    # Strip path traversal elements until none are left: one pass turns "....//" into "../".
    previous = None
    while cleaned != previous:
        previous = cleaned
        cleaned = PATH_TRAVERSAL_RE.sub("", cleaned)

    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned.strip()


# Firestore document ID rules: no "/", not "." or "..", not matching __.*__ (reserved).
# IDs here are interpolated into document paths (content_cache/{id},
# feed_items/{uid}_{id}), so an invalid one would otherwise surface as a 500.
DOCUMENT_ID_RE = re.compile(r"^[A-Za-z0-9_\-.:]+$")
RESERVED_DOCUMENT_ID_RE = re.compile(r"^__.*__$")


def is_valid_document_id(identifier: str) -> bool:
    """Return True if identifier is safe to use as (part of) a Firestore document ID."""
    return (
        bool(DOCUMENT_ID_RE.match(identifier))
        and identifier not in (".", "..")
        and not RESERVED_DOCUMENT_ID_RE.match(identifier)
    )


def sanitize_document_id(identifier: str | None, max_length: int = 200) -> str | None:
    """sanitize_identifier, then enforce Firestore document ID rules.

    Raises ValueError (surfaced as 400 VALIDATION_FAILED by Pydantic) on invalid input.
    """
    cleaned = sanitize_identifier(identifier, max_length=max_length)
    if cleaned is None:
        return None
    if not is_valid_document_id(cleaned):
        raise ValueError("must contain only letters, digits, '_', '-', '.', ':'")
    return cleaned


def sanitize_string_list(
    items: list[str] | None, max_item_length: int = 100, max_items: int = 50
) -> list[str]:
    """Sanitize a list of strings, removing empty elements and capping length."""
    if not items:
        return []

    result: list[str] = []
    for item in items:
        sanitized = sanitize_text(item, max_length=max_item_length)
        if sanitized:
            result.append(sanitized)
            if len(result) >= max_items:
                break

    return result
