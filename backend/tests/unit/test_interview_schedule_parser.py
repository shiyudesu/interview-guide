from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from interview_guide.common.ai.adapter import ChatResult, ProviderConfig
from interview_guide.common.ai.prompts import PromptSanitizer
from interview_guide.modules.interview_schedule.parser import (
    InterviewParseService,
)


class FakeRegistry:
    def __init__(self) -> None:
        self.requested: list[str | None] = []

    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        self.requested.append(provider_id)
        return ProviderConfig(
            provider_id=provider_id or "dashscope",
            base_url="https://example.test/v1",
            api_key="secret",
            model="model",
        )


class FakeAdapter:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[list[dict[str, str]]] = []

    async def chat(
        self,
        provider: ProviderConfig,
        messages: list[dict[str, str]],
    ) -> ChatResult:
        del provider
        self.messages.append(messages)
        return ChatResult(
            content=self.content,
            message={"content": self.content},
            usage=None,
            raw={},
        )


def service(
    content: str = "",
) -> tuple[
    InterviewParseService,
    FakeRegistry,
    FakeAdapter,
]:
    registry = FakeRegistry()
    adapter = FakeAdapter(content)
    parser = InterviewParseService(
        registry,  # type: ignore[arg-type]
        adapter,  # type: ignore[arg-type]
        PromptSanitizer(uuid_factory=lambda: uuid.UUID("12345678-0000-0000-0000-000000000000")),
        datetime(2026, 8, 16, 8, 0),
    )
    return parser, registry, adapter


@pytest.mark.asyncio
async def test_feishu_rule_parse_has_priority_over_ai() -> None:
    parser, registry, _ = service()
    raw = (
        "飞书 公司：字节跳动 岗位：Java工程师 "
        "时间：2026-08-20 10:30 第2轮 "
        "https://meeting.feishu.cn/fixed"
    )

    result = await parser.parse(raw, "feishu")

    assert result.success
    assert result.parse_method == "rule"
    assert result.confidence == 0.95
    assert result.data is not None
    assert result.data.company_name == "字节跳动"
    assert result.data.round_number == 2
    assert registry.requested == []


@pytest.mark.asyncio
async def test_chinese_round_preserves_compatibility_partial_parse_bug() -> None:
    parser, _, _ = service()
    raw = "公司：字节跳动 岗位：Java工程师 时间：2026-08-20 10:30 第二轮"

    result = await parser.parse(raw, "feishu")

    assert result.success
    assert result.data is not None
    assert result.data.interview_type is None


@pytest.mark.asyncio
async def test_tencent_meeting_text_preserves_duplicate_labels() -> None:
    parser, _, _ = service()
    raw = "腾讯会议 公司：腾讯 岗位：后端工程师 2026-08-20 10:30 会议号：123456789 密码：1234"

    result = await parser.parse(raw, "tencent")

    assert result.data is not None
    assert result.data.meeting_link == ("会议号: 会议号：123456789 密码: 密码：1234")


@pytest.mark.asyncio
async def test_ai_fallback_extracts_json_code_block_and_uses_source_as_provider() -> None:
    parser, registry, adapter = service(
        """```json
        {"companyName":"AI Corp","position":"Engineer",
        "interviewTime":"2026-08-21T09:30","roundNumber":"bad"}
        ```"""
    )

    result = await parser.parse("无法使用规则但包含足够信息", "custom-provider")

    assert result.success
    assert result.parse_method == "ai"
    assert result.data is not None
    assert result.data.round_number == 1
    assert registry.requested == ["custom-provider"]
    assert "当前日期 2026-08-16" in adapter.messages[0][0]["content"]
    assert "<data-boundary-12345678-parse-input>" in (adapter.messages[0][0]["content"])
