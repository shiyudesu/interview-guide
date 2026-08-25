from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from interview_guide.common.ai.user_providers import UserProviderRepository
from interview_guide.common.api.responses import STANDARD_ERROR_RESPONSES, result_response
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.result import Result
from interview_guide.modules.auth.dependencies import current_actor
from interview_guide.modules.llm_provider.models import (
    AsrConfigRequest,
    AsrConfigResponse,
    CreateProviderRequest,
    DefaultProviderRequest,
    ModelDiscoveryRequest,
    ProviderModelList,
    ProviderResponse,
    ProviderTestResult,
    TtsConfigRequest,
    TtsConfigResponse,
    UpdateProviderRequest,
)
from interview_guide.modules.llm_provider.service import LlmProviderService
from interview_guide.modules.llm_provider.voice import VoiceConfigService

router = APIRouter(prefix="/api/llm-provider", responses=STANDARD_ERROR_RESPONSES)


async def provider_service(request: Request) -> LlmProviderService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    actor = current_actor(request)
    repository = UserProviderRepository(infrastructure.database.sessions, actor.user_id)
    return LlmProviderService(
        repository,
        infrastructure.provider_resolver.for_user(actor.user_id),
        infrastructure.api_key_encryption,
        request.app.state.settings,
        infrastructure.redis.client,
        infrastructure.provider_outbound_policy,
    )


ServiceDependency = Annotated[LlmProviderService, Depends(provider_service)]


def scoped_voice_service(request: Request) -> VoiceConfigService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    actor = current_actor(request)
    repository = UserProviderRepository(infrastructure.database.sessions, actor.user_id)
    return VoiceConfigService(
        repository,
        infrastructure.provider_resolver.for_user(actor.user_id),
        infrastructure.api_key_encryption,
        infrastructure.provider_outbound_policy,
    )


VoiceServiceDependency = Annotated[VoiceConfigService, Depends(scoped_voice_service)]


@router.get("/list", response_model=list[ProviderResponse])
async def list_providers(service: ServiceDependency) -> Response:
    return result_response(Result.ok(await service.list()))


@router.get("/voice/asr", response_model=AsrConfigResponse)
async def get_asr_config(service: VoiceServiceDependency) -> Response:
    return result_response(Result.ok(await service.asr()))


@router.put("/voice/asr", status_code=204)
async def update_asr_config(
    payload: AsrConfigRequest,
    service: VoiceServiceDependency,
) -> Response:
    await service.update_asr(payload)
    return result_response(Result.ok())


@router.get("/voice/tts", response_model=TtsConfigResponse)
async def get_tts_config(service: VoiceServiceDependency) -> Response:
    return result_response(Result.ok(await service.tts()))


@router.put("/voice/tts", status_code=204)
async def update_tts_config(
    payload: TtsConfigRequest,
    service: VoiceServiceDependency,
) -> Response:
    await service.update_tts(payload)
    return result_response(Result.ok())


@router.post("/voice/asr/test", response_model=ProviderTestResult)
async def test_asr_config(service: VoiceServiceDependency) -> Response:
    return result_response(Result.ok(await service.test_asr()))


@router.post("/reload", status_code=204)
async def reload_providers(service: ServiceDependency) -> Response:
    await service.reload()
    return result_response(Result.ok())


@router.post("/models/discover", response_model=ProviderModelList)
async def discover_provider_models(
    payload: ModelDiscoveryRequest,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.discover_models(payload)))


@router.post("", status_code=204)
async def create_provider(
    payload: CreateProviderRequest,
    service: ServiceDependency,
) -> Response:
    await service.create(payload)
    return result_response(Result.ok())


@router.get("/default-provider", response_model=DefaultProviderRequest)
async def get_default_provider(service: ServiceDependency) -> Response:
    return result_response(Result.ok(await service.defaults()))


@router.put("/default-provider", status_code=204)
async def update_default_provider(
    payload: DefaultProviderRequest,
    service: ServiceDependency,
) -> Response:
    await service.update_default_chat(payload)
    return result_response(Result.ok())


@router.put("/default-embedding-provider", status_code=204)
async def update_default_embedding_provider(
    payload: DefaultProviderRequest,
    service: ServiceDependency,
) -> Response:
    await service.update_default_embedding(payload)
    return result_response(Result.ok())


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.get(provider_id)))


@router.post("/{provider_id}/test", response_model=ProviderTestResult)
async def test_provider(
    provider_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.test(provider_id)))


@router.put("/{provider_id}", status_code=204)
async def update_provider(
    provider_id: str,
    payload: UpdateProviderRequest,
    service: ServiceDependency,
) -> Response:
    await service.update(provider_id, payload)
    return result_response(Result.ok())


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: str,
    service: ServiceDependency,
) -> Response:
    await service.delete(provider_id)
    return result_response(Result.ok())
