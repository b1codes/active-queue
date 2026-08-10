from __future__ import annotations

from app.core.sanitizer import (
    sanitize_identifier,
    sanitize_string_list,
    sanitize_text,
    sanitize_url,
)


def test_sanitize_text_basic() -> None:
    """sanitize_text strips whitespace, control characters, and HTML tags."""
    assert sanitize_text("  hello world  ") == "hello world"
    assert sanitize_text("hello\x00world\x07!") == "helloworld!"
    assert sanitize_text("<script>alert('xss')</script>Hello") == "Hello"
    assert sanitize_text("<b style='color:red;'>Bold</b>") == "Bold"
    assert sanitize_text(None) is None


def test_sanitize_text_max_length() -> None:
    """sanitize_text truncates output to max_length."""
    text = "a" * 100
    assert len(sanitize_text(text, max_length=10) or "") == 10


def test_sanitize_url_valid() -> None:
    """sanitize_url allows valid http and https URLs."""
    assert sanitize_url("https://www.youtube.com/playlist?list=PL123") == "https://www.youtube.com/playlist?list=PL123"
    assert sanitize_url("http://example.com/feed") == "http://example.com/feed"


def test_sanitize_url_invalid_schemes() -> None:
    """sanitize_url rejects dangerous schemes (javascript:, data:, vbscript:, file:)."""
    assert sanitize_url("javascript:alert(1)") is None
    assert sanitize_url("data:text/html,<script>alert(1)</script>") is None
    assert sanitize_url("file:///etc/passwd") is None
    assert sanitize_url("  JAVAscript:void(0) ") is None


def test_sanitize_url_control_chars() -> None:
    """sanitize_url strips control characters and null bytes."""
    assert sanitize_url("https://example.com/path\x00\x07") == "https://example.com/path"


def test_sanitize_identifier_path_traversal() -> None:
    """sanitize_identifier strips path traversal sequences (../, ..\\)."""
    assert sanitize_identifier("../../../etc/passwd") == "etc/passwd"
    assert sanitize_identifier("..\\..\\windows\\system32") == "windows\\system32"
    assert sanitize_identifier("yt:video_123") == "yt:video_123"
    assert sanitize_identifier(None) is None


def test_sanitize_string_list() -> None:
    """sanitize_string_list sanitizes elements, removes empty elements, and respects caps."""
    raw = ["  running  ", "<script>bad</script>", "  ", "strength\x00"]
    result = sanitize_string_list(raw, max_item_length=20, max_items=2)
    assert result == ["running", "strength"]
