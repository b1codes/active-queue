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


def sanitize_text(text: str | None, max_length: int | None = None) -> str | None:
    """Sanitize free-text input by stripping control chars, null bytes, HTML tags, and trailing spaces."""
    if text is None:
        return None

    cleaned = text.strip()
    if not cleaned:
        return ""

    # Strip script/style/iframe tags and their content
    cleaned = SCRIPT_TAG_RE.sub("", cleaned)

    # Strip null bytes and control characters
    cleaned = CONTROL_CHAR_RE.sub("", cleaned)

    # Strip remaining HTML tags
    cleaned = HTML_TAG_RE.sub("", cleaned)

    # Remove inline dangerous script protocols if present
    cleaned = DANGEROUS_SCHEME_RE.sub("", cleaned)

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
    cleaned = CONTROL_CHAR_RE.sub("", cleaned)

    if len(cleaned) > max_length:
        return None

    # Reject dangerous schemes
    if DANGEROUS_SCHEME_RE.search(cleaned):
        return None

    parsed = urlparse(cleaned)
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

    # Strip path traversal elements
    cleaned = PATH_TRAVERSAL_RE.sub("", cleaned)

    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned.strip()


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

