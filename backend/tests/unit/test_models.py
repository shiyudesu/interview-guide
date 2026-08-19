from __future__ import annotations

from datetime import datetime

import pytest

from interview_guide.common.api.models import (
    CamelModel,
    compact_json_text,
    format_api_datetime,
    normalize_request_id,
    utf16_code_unit_length,
)
from interview_guide.common.result import Result


class ExampleModel(CamelModel):
    created_at: datetime
    session_id: int


def test_result_field_order_matches_compatibility_json() -> None:
    result = Result.ok({"status": "UP"})

    assert list(result.model_dump().keys()) == [
        "code",
        "data",
        "message",
        "success",
    ]


def test_camel_case_and_datetime_helpers() -> None:
    model = ExampleModel(
        created_at=datetime(2026, 8, 16, 8, 0),
        session_id=9,
    )

    assert model.model_dump(by_alias=True) == {
        "createdAt": datetime(2026, 8, 16, 8, 0),
        "sessionId": 9,
    }
    assert format_api_datetime(model.created_at) == "2026-08-16T08:00:00"


def test_compatibility_utf16_length_counts_surrogate_pairs() -> None:
    assert utf16_code_unit_length("A😀B") == 4


def test_compact_json_preserves_unicode_and_insertion_order() -> None:
    assert compact_json_text({"message": "中文", "score": 1}) == ('{"message":"中文","score":1}')


@pytest.mark.parametrize("value", ["short", "contains space", "symbols!"])
def test_request_id_rejects_contract_incompatible_values(value: str) -> None:
    with pytest.raises(ValueError, match="requestId格式不正确"):
        normalize_request_id(value)


def test_request_id_accepts_contract_pattern() -> None:
    assert normalize_request_id("request_123") == "request_123"
