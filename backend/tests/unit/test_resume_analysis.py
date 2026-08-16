from __future__ import annotations

from pathlib import Path

import pytest

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.prompts import PromptRepository
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.resume.analysis import ResumeGradingService

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class FakeRegistry:
    async def get_chat(self) -> ProviderConfig:
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
async def test_ai_failure_returns_java_zero_score_result() -> None:
    service = ResumeGradingService(
        FakeRegistry(),  # type: ignore[arg-type]
        FailingStructuredOutput(),  # type: ignore[arg-type]
        PromptRepository(BACKEND_ROOT / "resources"),
    )

    result = await service.analyze("Fixed resume")

    assert result.output.overallScore == 0
    assert result.output.scoreDetail.model_dump() == {
        "contentScore": 0,
        "structureScore": 0,
        "skillMatchScore": 0,
        "expressionScore": 0,
        "projectScore": 0,
    }
    assert result.output.summary == (
        "分析过程中出现错误: 简历分析失败：简历分析失败：Request failed"
    )
    assert result.output.strengths == []
    assert result.output.suggestions[0].model_dump() == {
        "category": "系统",
        "priority": "高",
        "issue": "AI分析服务暂时不可用",
        "recommendation": "请稍后重试，或检查AI服务是否正常运行",
    }
