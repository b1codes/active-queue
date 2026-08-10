from __future__ import annotations

from app.middleware.ratelimit import LIMIT_GENERAL, LIMIT_SYNC, FixedWindowRateLimiter


def test_fixed_window_rate_limiter_general_limit() -> None:
    """FixedWindowRateLimiter enforces 60 req/min general limit."""
    limiter = FixedWindowRateLimiter()
    now = 1000.0

    # 60 requests should pass
    for i in range(LIMIT_GENERAL):
        allowed, limit, remaining, reset_secs = limiter.check_and_increment(
            "user_gen_1", is_sync_endpoint=False, now=now
        )
        assert allowed is True
        assert limit == 60
        assert remaining == 60 - (i + 1)
        assert reset_secs > 0

    # 61st request should be rejected
    allowed, limit, remaining, reset_secs = limiter.check_and_increment(
        "user_gen_1", is_sync_endpoint=False, now=now
    )
    assert allowed is False
    assert limit == 60
    assert remaining == 0
    assert reset_secs > 0


def test_fixed_window_rate_limiter_sync_limit() -> None:
    """FixedWindowRateLimiter enforces 10 req/min sync endpoint limit."""
    limiter = FixedWindowRateLimiter()
    now = 1000.0

    # 10 sync requests should pass
    for i in range(LIMIT_SYNC):
        allowed, limit, remaining, _reset_secs = limiter.check_and_increment(
            "user_sync_1", is_sync_endpoint=True, now=now
        )
        assert allowed is True
        assert limit == 10
        assert remaining == 10 - (i + 1)

    # 11th request should be rejected
    allowed, limit, remaining, _reset_secs = limiter.check_and_increment(
        "user_sync_1", is_sync_endpoint=True, now=now
    )
    assert allowed is False
    assert limit == 10
    assert remaining == 0


def test_fixed_window_rate_limiter_window_reset() -> None:
    """Rate limit counts reset when moving to next 60s window."""
    limiter = FixedWindowRateLimiter()
    t1 = 1000.0

    # Exhaust limit in window 1
    for _ in range(LIMIT_GENERAL):
        limiter.check_and_increment("user_reset", is_sync_endpoint=False, now=t1)

    # 61st request fails
    allowed_t1, _, _, _ = limiter.check_and_increment("user_reset", is_sync_endpoint=False, now=t1)
    assert allowed_t1 is False

    # Move to next window (t1 + 65s)
    t2 = t1 + 65.0
    allowed_t2, _limit, remaining, _ = limiter.check_and_increment(
        "user_reset", is_sync_endpoint=False, now=t2
    )
    assert allowed_t2 is True
    assert remaining == 59
