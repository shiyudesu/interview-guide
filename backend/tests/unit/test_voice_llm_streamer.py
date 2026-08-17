from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any, cast

import pytest

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.prompts import PromptSanitizer
from interview_guide.common.ai.skills import SkillRepository
from interview_guide.common.db.models import (
    VoiceInterviewMessage,
    VoiceInterviewSession,
)
from interview_guide.modules.voice_interview.context import (
    CompressedHistory,
    VoiceContextCompressor,
)
from interview_guide.modules.voice_interview.llm import UnifiedVoiceLlmStreamer
from interview_guide.modules.voice_interview.repository import VoiceInterviewRepository


class FakeRepository:
    async def messages(self, session_id: int) -> list[VoiceInterviewMessage]:
        del session_id
        return []

    async def summary_row(self, session_id: int) -> VoiceInterviewMessage | None:
        del session_id
        return None

    async def save_summary(
        self,
        session_id: int,
        summary: str,
        covered_turns: int,
    ) -> None:
        del session_id, summary, covered_turns

    async def resume_text(self, resume_id: int | None) -> str | None:
        del resume_id
        return None


class FakeRegistry:
    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        del provider_id
        return ProviderConfig(
            provider_id="explicit-fake",
            base_url="http://127.0.0.1",
            api_key="explicit-fake",
            model="explicit-fake",
        )


class FakeCompressor:
    async def compress(
        self,
        turns: list[VoiceInterviewMessage],
        cached_summary: str | None,
        covered_turns: int,
        provider_id: str | None,
    ) -> CompressedHistory:
        del cached_summary, covered_turns, provider_id
        return CompressedHistory(None, turns, len(turns), False)

    @staticmethod
    def format_recent(turns: list[VoiceInterviewMessage]) -> list[str]:
        del turns
        return []


class FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []

    async def stream_chat(
        self,
        provider: ProviderConfig,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        del provider, temperature
        assert tools is not None
        assert tool_choice == "auto"
        self.calls.append([dict(message) for message in messages])
        if len(self.calls) == 1:
            yield {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call-1",
                                    "function": {
                                        "name": "Skill",
                                        "arguments": '{"command":"java-backend"}',
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        else:
            yield {"choices": [{"delta": {"content": "请介绍事务。"}}]}


@pytest.mark.asyncio
async def test_voice_llm_streamer_executes_skill_tool_before_text() -> None:
    resources = Path(__file__).resolve().parents[2] / "resources"
    adapter = FakeAdapter()
    streamer = UnifiedVoiceLlmStreamer(
        cast(VoiceInterviewRepository, FakeRepository()),
        cast(Any, FakeRegistry()),
        cast(Any, adapter),
        PromptSanitizer(uuid_factory=lambda: uuid.UUID("00000000-0000-0000-0000-000000000000")),
        SkillRepository(resources),
        cast(VoiceContextCompressor, FakeCompressor()),
    )
    session = VoiceInterviewSession(
        id=1,
        role_type="java-backend",
        skill_id="java-backend",
        status="IN_PROGRESS",
        current_phase="TECH",
        llm_provider="dashscope",
    )

    chunks = [chunk async for chunk in streamer.stream(session, "事务是什么？")]

    assert chunks == ["请介绍事务。"]
    assert len(adapter.calls) == 2
    tool_result = adapter.calls[1][-1]
    assert tool_result["role"] == "tool"
    assert tool_result["tool_call_id"] == "call-1"
    assert "Java" in str(tool_result["content"])
