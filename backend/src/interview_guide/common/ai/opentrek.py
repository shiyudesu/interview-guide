from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from interview_guide.common.ai.adapter import ProviderConfig
from interview_guide.common.ai.providers import ProviderRegistry
from interview_guide.common.config.settings import Settings


class OpenTrekCapability(StrEnum):
    GENERAL = "general"
    INTERVIEWER = "interviewer"
    EVALUATOR = "evaluator"
    RAG = "rag"


@dataclass(frozen=True)
class OpenTrekAgentTarget:
    capability: OpenTrekCapability
    agent_code: str
    agent_version: str | None


@dataclass(frozen=True)
class OpenTrekProviderConfig(ProviderConfig):
    capability: OpenTrekCapability = OpenTrekCapability.GENERAL
    agent_version: str | None = None
    skill_names: tuple[str, ...] = ()
    structured_security_boundary: bool = True
    structured_duplicate_schema: bool = True
    structured_compact_schema: bool = False


def opentrek_provider_with_skills(
    provider: ProviderConfig,
    *skill_names: str | None,
) -> ProviderConfig:
    if not isinstance(provider, OpenTrekProviderConfig):
        return provider
    normalized = tuple(
        dict.fromkeys(value.strip() for value in skill_names if value is not None and value.strip())
    )
    return replace(provider, skill_names=normalized)


def opentrek_provider_for_kb_question_generation(
    provider: ProviderConfig,
) -> ProviderConfig:
    if not isinstance(provider, OpenTrekProviderConfig):
        return provider
    return replace(
        provider,
        structured_security_boundary=False,
        structured_duplicate_schema=False,
        structured_compact_schema=True,
    )


def opentrek_agent_target(
    settings: Settings,
    capability: OpenTrekCapability,
) -> OpenTrekAgentTarget:
    values = {
        OpenTrekCapability.GENERAL: (
            settings.opentrek_general_agent_code,
            settings.opentrek_general_agent_version,
        ),
        OpenTrekCapability.INTERVIEWER: (
            settings.opentrek_interviewer_agent_code,
            settings.opentrek_interviewer_agent_version,
        ),
        OpenTrekCapability.EVALUATOR: (
            settings.opentrek_evaluator_agent_code,
            settings.opentrek_evaluator_agent_version,
        ),
        OpenTrekCapability.RAG: (
            settings.opentrek_rag_agent_code,
            settings.opentrek_rag_agent_version,
        ),
    }
    agent_code, agent_version = values[capability]
    return OpenTrekAgentTarget(
        capability=capability,
        agent_code=agent_code.strip(),
        agent_version=agent_version.strip() or None,
    )


class OpenTrekProviderRegistry:
    def __init__(
        self,
        delegate: ProviderRegistry,
        settings: Settings,
        capability: OpenTrekCapability,
    ) -> None:
        self._delegate = delegate
        self._settings = settings
        self._target = opentrek_agent_target(settings, capability)

    async def default_chat_alias(self) -> str:
        return await self._delegate.default_chat_alias()

    async def default_embedding_alias(self) -> str:
        return await self._delegate.default_embedding_alias()

    async def get_chat(self, provider_id: str | None = None) -> ProviderConfig:
        del provider_id
        return OpenTrekProviderConfig(
            provider_id=f"opentrek:{self._target.capability.value}",
            base_url=self._settings.opentrek_runtime_base_url.strip().rstrip("/"),
            api_key=self._settings.opentrek_app_key.get_secret_value(),
            model=self._target.agent_code,
            supports_embedding=False,
            capability=self._target.capability,
            agent_version=self._target.agent_version,
        )

    async def get_embedding(self, provider_id: str | None = None) -> ProviderConfig:
        return await self._delegate.get_embedding(provider_id)

    async def get_voice(self, provider_id: str) -> ProviderConfig:
        return await self._delegate.get_voice(provider_id)

    async def publish_change(self) -> int:
        return await self._delegate.publish_change()

    async def reload(self) -> None:
        await self._delegate.reload()
