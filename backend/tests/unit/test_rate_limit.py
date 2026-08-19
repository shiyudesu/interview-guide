from __future__ import annotations

from interview_guide.common.redis.rate_limit import (
    RateLimitDimension,
    RateLimiter,
)


def test_rate_limit_keys_keep_compatibility_class_and_method_names() -> None:
    assert (
        RateLimiter._key(
            "KnowledgeBaseController",
            "queryKnowledgeBase",
            RateLimitDimension.GLOBAL,
            "127.0.0.1",
            "anonymous",
        )
        == "ratelimit:{KnowledgeBaseController:queryKnowledgeBase}:global"
    )
    assert (
        RateLimiter._key(
            "KnowledgeBaseController",
            "queryKnowledgeBase",
            RateLimitDimension.IP,
            "127.0.0.1",
            "anonymous",
        )
        == "ratelimit:{KnowledgeBaseController:queryKnowledgeBase}:ip:127.0.0.1"
    )
