from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from interview_guide.common.ai.opentrek import (
    OpenTrekCapability,
    OpenTrekProviderConfig,
)
from interview_guide.common.config.settings import Settings
from interview_guide.common.db.models import KnowledgeBase
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.infrastructure.opentrek.client import OpenTrekClient
from interview_guide.modules.knowledge_base.repository import VectorSearchHit


@dataclass(frozen=True)
class MappedKnowledgeBase:
    local_id: int
    kb_code: str


@dataclass(frozen=True)
class KortexDocument:
    local_id: int
    content: str
    score: float


class KortexMappingResolver(Protocol):
    async def resolve(self, knowledge_base_ids: Sequence[int]) -> list[MappedKnowledgeBase]: ...


class KortexGateway(Protocol):
    async def post_json(
        self,
        provider: OpenTrekProviderConfig,
        path: str,
        payload: dict[str, Any],
        *,
        workspace_code: str | None = None,
    ) -> dict[str, Any]: ...


class DatabaseKortexMappingResolver:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        user_id: UUID,
        mappings: dict[str, str],
    ) -> None:
        self._sessions = sessions
        self._user_id = user_id
        self._mappings = mappings

    async def resolve(self, knowledge_base_ids: Sequence[int]) -> list[MappedKnowledgeBase]:
        unique_ids = list(dict.fromkeys(knowledge_base_ids))
        async with self._sessions() as session:
            rows = await session.execute(
                select(KnowledgeBase.id, KnowledgeBase.file_hash).where(
                    KnowledgeBase.user_id == self._user_id,
                    KnowledgeBase.id.in_(unique_ids),
                )
            )
        hashes = {int(local_id): str(file_hash).lower() for local_id, file_hash in rows}
        for local_id in unique_ids:
            if local_id not in hashes:
                raise BusinessException(ErrorCode.NOT_FOUND, f"知识库不存在: {local_id}")
        result: list[MappedKnowledgeBase] = []
        for local_id in unique_ids:
            kb_code = self._mappings.get(hashes[local_id])
            if kb_code is None:
                raise BusinessException(
                    ErrorCode.KNOWLEDGE_BASE_QUERY_FAILED,
                    f"知识库 {local_id} 未配置 OpenTrek Kortex 映射",
                )
            result.append(MappedKnowledgeBase(local_id, kb_code))
        return result


class OpenTrekKortexClient:
    def __init__(
        self,
        settings: Settings,
        gateway: KortexGateway,
    ) -> None:
        self._settings = settings
        self._gateway = gateway
        self._provider = OpenTrekProviderConfig(
            provider_id="opentrek:kortex",
            base_url=settings.opentrek_runtime_base_url.strip().rstrip("/"),
            api_key=settings.opentrek_app_key.get_secret_value(),
            model=settings.opentrek_rag_agent_code,
            capability=OpenTrekCapability.RAG,
            agent_version=settings.opentrek_rag_agent_version.strip() or None,
        )

    async def retrieve(
        self,
        knowledge_bases: Sequence[MappedKnowledgeBase],
        query: str,
        top_k: int,
        min_score: float,
    ) -> list[KortexDocument]:
        documents: list[KortexDocument] = []
        batch_size = self._settings.opentrek_kb_batch_size
        for start in range(0, len(knowledge_bases), batch_size):
            batch = knowledge_bases[start : start + batch_size]
            document = await self._gateway.post_json(
                self._provider,
                "kortex/api/kb/doc/combination/retrieve",
                {
                    "combinationParams": [
                        {
                            "kbCode": knowledge_base.kb_code,
                            "query": query,
                            "score": min_score,
                            "limit": max(top_k, 1),
                            "mapBatchKey": str(knowledge_base.local_id),
                            "kbIndexEngineType": "builtin_vector",
                            "needFileInfo": False,
                        }
                        for knowledge_base in batch
                    ]
                },
                workspace_code=self._settings.opentrek_workspace_code,
            )
            documents.extend(self._parse_batch(document, batch))
        return documents

    @staticmethod
    def _parse_batch(
        document: dict[str, Any],
        batch: Sequence[MappedKnowledgeBase],
    ) -> list[KortexDocument]:
        data = document.get("data")
        if not isinstance(data, list):
            raise BusinessException(
                ErrorCode.KNOWLEDGE_BASE_QUERY_FAILED,
                "Kortex 批量检索返回结构无效",
            )
        allowed = {str(item.local_id): item for item in batch}
        parsed: list[KortexDocument] = []
        for group in data:
            if not isinstance(group, dict):
                raise BusinessException(
                    ErrorCode.KNOWLEDGE_BASE_QUERY_FAILED,
                    "Kortex 批量检索返回结构无效",
                )
            if group.get("success") is False:
                detail = str(group.get("errorMessage") or "未知错误")[:300]
                raise BusinessException(
                    ErrorCode.KNOWLEDGE_BASE_QUERY_FAILED,
                    f"Kortex 检索失败：{detail}",
                )
            key = str(group.get("mapBatchKey") or "")
            mapped = allowed.get(key)
            if mapped is None:
                raise BusinessException(
                    ErrorCode.KNOWLEDGE_BASE_QUERY_FAILED,
                    "Kortex 返回了未知的知识库映射键",
                )
            results = group.get("result")
            if results is None:
                continue
            if not isinstance(results, list):
                raise BusinessException(
                    ErrorCode.KNOWLEDGE_BASE_QUERY_FAILED,
                    "Kortex 检索结果结构无效",
                )
            for item in results:
                if not isinstance(item, dict):
                    continue
                content = item.get("chunk_content")
                score = item.get("score")
                if not isinstance(content, str) or not content.strip():
                    continue
                try:
                    numeric_score = float(cast(float | int | str, score))
                except (TypeError, ValueError):
                    continue
                parsed.append(KortexDocument(mapped.local_id, content, numeric_score))
        return parsed


class KortexRetriever:
    def __init__(
        self,
        resolver: KortexMappingResolver,
        client: OpenTrekKortexClient,
    ) -> None:
        self._resolver = resolver
        self._client = client

    async def retrieve(
        self,
        knowledge_base_ids: Sequence[int],
        query: str,
        top_k: int,
        min_score: float,
    ) -> list[VectorSearchHit]:
        mappings = await self._resolver.resolve(knowledge_base_ids)
        raw = await self._client.retrieve(mappings, query, top_k, min_score)
        best_by_content: dict[str, KortexDocument] = {}
        for document in raw:
            key = " ".join(document.content.split()).casefold()
            previous = best_by_content.get(key)
            if previous is None or document.score > previous.score:
                best_by_content[key] = document
        ordered = sorted(
            best_by_content.values(),
            key=lambda item: (-item.score, item.local_id, item.content),
        )[: max(top_k, 1)]
        return [
            VectorSearchHit(
                content=item.content,
                score=item.score,
                knowledge_base_id=item.local_id,
            )
            for item in ordered
        ]


def build_kortex_retriever(
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
    user_id: UUID,
    gateway: OpenTrekClient,
) -> KortexRetriever:
    return KortexRetriever(
        DatabaseKortexMappingResolver(sessions, user_id, settings.opentrek_kb_mappings),
        OpenTrekKortexClient(settings, gateway),
    )
