from __future__ import annotations

from pathlib import Path

import pytest

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.resume.analysis import ResumeGradingService

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class FakeRegistry:
    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        del provider_id
        return ProviderConfig(
            provider_id="test",
            base_url="https://example.test/v1",
            api_key="secret",
            model="test",
        )


class FailingStructuredOutput:
    async def invoke(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        raise BusinessException(
            ErrorCode.RESUME_ANALYSIS_FAILED,
            "简历分析失败：Request failed",
        )


@pytest.mark.asyncio
async def test_ai_failure_is_propagated_for_stream_retry() -> None:
    service = ResumeGradingService(
        FakeRegistry(),  # type: ignore[arg-type]
        FailingStructuredOutput(),  # type: ignore[arg-type]
        PromptRepository(BACKEND_ROOT / "resources"),
    )

    with pytest.raises(BusinessException, match="简历分析失败：Request failed"):
        await service.analyze("Fixed resume")
