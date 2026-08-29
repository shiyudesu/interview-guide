from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from interview_guide.common.ai.opentrek import OpenTrekProviderConfig
from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.infrastructure.opentrek.kortex import (
    KortexRetriever,
    MappedKnowledgeBase,
    OpenTrekKortexClient,
)


def settings() -> Settings:
    return Settings(
        APP_OPENTREK_ENABLED=True,
        APP_OPENTREK_APP_KEY="protected-app-key",
        APP_OPENTREK_WORKSPACE_CODE="competition",
        APP_OPENTREK_GENERAL_AGENT_CODE="general-code",
        APP_OPENTREK_INTERVIEWER_AGENT_CODE="interviewer-code",
        APP_OPENTREK_EVALUATOR_AGENT_CODE="evaluator-code",
        APP_OPENTREK_RAG_AGENT_CODE="rag-code",
        APP_PROVIDER_OUTBOUND_ALLOWED_HOSTS="10.128.203.200",
        APP_PROVIDER_OUTBOUND_ALLOWED_NETWORKS="10.128.203.200/32",
    )


class StubResolver:
    def __init__(self, values: Sequence[MappedKnowledgeBase]) -> None:
        self.values = list(values)
        self.requested_ids: list[int] = []

    async def resolve(self, knowledge_base_ids: Sequence[int]) -> list[MappedKnowledgeBase]:
        self.requested_ids = list(knowledge_base_ids)
        return self.values


class RecordingGateway:
    def __init__(self, *, failing: bool = False) -> None:
        self.calls: list[tuple[OpenTrekProviderConfig, str, dict[str, Any], str | None]] = []
        self.failing = failing

    async def post_json(
        self,
        provider: OpenTrekProviderConfig,
        path: str,
        payload: dict[str, Any],
        *,
        workspace_code: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append((provider, path, payload, workspace_code))
        groups: list[dict[str, Any]] = []
        for index, item in enumerate(payload["combinationParams"]):
            if self.failing:
                groups.append(
                    {
                        "mapBatchKey": item["mapBatchKey"],
                        "success": False,
                        "errorMessage": "retrieval unavailable",
                    }
                )
                continue
            groups.append(
                {
                    "mapBatchKey": item["mapBatchKey"],
                    "kbCode": item["kbCode"],
                    "success": True,
                    "result": [
                        {
                            "chunk_content": "重复内容" if index == 0 else f"内容-{item['kbCode']}",
                            "score": 0.5 + index / 100,
                        },
                        {
                            "chunk_content": "重复内容",
                            "score": 0.9 if index == 1 else 0.4,
                        },
                    ],
                }
            )
        return {"success": True, "data": groups}


async def test_kortex_batches_maps_deduplicates_and_sorts() -> None:
    mappings = [MappedKnowledgeBase(index, f"kb-{index}") for index in range(1, 13)]
    resolver = StubResolver(mappings)
    gateway = RecordingGateway()
    retriever = KortexRetriever(resolver, OpenTrekKortexClient(settings(), gateway))

    hits = await retriever.retrieve([item.local_id for item in mappings], "问题", 20, 0.28)

    assert resolver.requested_ids == list(range(1, 13))
    assert len(gateway.calls) == 2
    assert len(gateway.calls[0][2]["combinationParams"]) == 10
    assert len(gateway.calls[1][2]["combinationParams"]) == 2
    assert all(call[1] == "kortex/api/kb/doc/combination/retrieve" for call in gateway.calls)
    assert all(call[3] == "competition" for call in gateway.calls)
    assert all(
        item["score"] == 0.28
        and item["limit"] == 20
        and item["needFileInfo"] is False
        for call in gateway.calls
        for item in call[2]["combinationParams"]
    )
    assert sum(hit.content == "重复内容" for hit in hits) == 1
    assert hits[0].content == "重复内容"
    assert hits[0].score == 0.9


async def test_kortex_batch_failure_is_explicit() -> None:
    gateway = RecordingGateway(failing=True)
    retriever = KortexRetriever(
        StubResolver([MappedKnowledgeBase(1, "kb-one")]),
        OpenTrekKortexClient(settings(), gateway),
    )

    with pytest.raises(BusinessException) as caught:
        await retriever.retrieve([1], "问题", 10, 0.2)

    assert caught.value.code == ErrorCode.KNOWLEDGE_BASE_QUERY_FAILED.code
    assert "retrieval unavailable" in caught.value.message


async def test_kortex_rejects_unknown_mapping_key() -> None:
    class InvalidGateway(RecordingGateway):
        async def post_json(
            self,
            provider: OpenTrekProviderConfig,
            path: str,
            payload: dict[str, Any],
            *,
            workspace_code: str | None = None,
        ) -> dict[str, Any]:
            del provider, path, payload, workspace_code
            return {"success": True, "data": [{"mapBatchKey": "other", "result": []}]}

    retriever = KortexRetriever(
        StubResolver([MappedKnowledgeBase(1, "kb-one")]),
        OpenTrekKortexClient(settings(), InvalidGateway()),
    )

    with pytest.raises(BusinessException, match="映射键"):
        await retriever.retrieve([1], "问题", 10, 0.2)
