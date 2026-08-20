from __future__ import annotations

from interview_guide.common.redis.rate_limit import (
    RateLimitDimension,
    RateLimiter,
)


def test_rate_limit_keys_use_business_scope() -> None:
    assert (
        RateLimiter._key(
            "knowledge-base:query",
            RateLimitDimension.GLOBAL,
            "127.0.0.1",
            "anonymous",
        )
        == "ratelimit:{knowledge-base:query}:global"
    )
    assert (
        RateLimiter._key(
            "knowledge-base:query",
            RateLimitDimension.IP,
            "127.0.0.1",
            "anonymous",
        )
        == "ratelimit:{knowledge-base:query}:ip:127.0.0.1"
    )
