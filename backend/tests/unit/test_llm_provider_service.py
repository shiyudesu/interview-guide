from __future__ import annotations

from interview_guide.modules.llm_provider.service import mask_api_key


def test_api_key_mask_matches_java() -> None:
    assert mask_api_key(None) == "***"
    assert mask_api_key("") == "***"
    assert mask_api_key("123456") == "***"
    assert mask_api_key("1234567") == "123***567"
