from __future__ import annotations

from types import SimpleNamespace

import pytest

from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.knowledge_base.api import require_knowledge_base_writes


def request_for(competition_mode: bool) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=Settings(
                    _env_file=None,
                    APP_COMPETITION_MODE=competition_mode,
                )
            )
        )
    )


def test_standard_mode_allows_knowledge_base_writes() -> None:
    require_knowledge_base_writes(request_for(False))  # type: ignore[arg-type]


def test_competition_mode_rejects_knowledge_base_writes() -> None:
    with pytest.raises(BusinessException) as caught:
        require_knowledge_base_writes(request_for(True))  # type: ignore[arg-type]

    assert caught.value.code == ErrorCode.FORBIDDEN.code
    assert "预置只读" in caught.value.message
