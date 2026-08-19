from __future__ import annotations

from interview_guide.common.ai.providers import static_provider_seeds
from interview_guide.common.config.settings import Settings


def test_static_provider_seed_order_and_defaults_match_compatibility() -> None:
    settings = Settings(
        _env_file=None,
        APP_AI_CONFIG_ENCRYPTION_KEY="test-key",
        AI_BAILIAN_API_KEY="dashscope-key",
        AI_EMBEDDING_MODEL="qwen-embedding-test",
        AI_MODEL="qwen-test",
        PROVIDER_KIMI_API_KEY="kimi-key",
    )

    seeds = static_provider_seeds(settings)

    assert [seed.provider_id for seed in seeds] == [
        "dashscope",
        "lmstudio",
        "kimi",
        "deepseek",
        "glm",
    ]
    assert seeds[0].model == "qwen-test"
    assert seeds[0].embedding_model == "qwen-embedding-test"
    assert seeds[2].temperature == 1
