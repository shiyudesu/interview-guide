from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from interview_guide.common.api.responses import result_response
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.common.result import Result
from interview_guide.modules.llm_provider.models import (
    AsrConfigRequest,
    CreateProviderRequest,
    DefaultProviderRequest,
    ModelDiscoveryRequest,
    TtsConfigRequest,
    UpdateProviderRequest,
)
from interview_guide.modules.llm_provider.service import LlmProviderService

router = APIRouter(prefix="/api/llm-provider")


async def provider_service(request: Request) -> LlmProviderService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    return LlmProviderService(
        infrastructure.provider_repository,
        infrastructure.provider_registry,
        infrastructure.api_key_encryption,
        request.app.state.settings,
        infrastructure.redis.client,
    )


ServiceDependency = Annotated[LlmProviderService, Depends(provider_service)]


@router.get("/list")
async def list_providers(service: ServiceDependency) -> Response:
    return result_response(Result.ok(await service.list()))


@router.get("/voice/asr")
async def get_asr_config(request: Request) -> Response:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    return result_response(Result.ok(await infrastructure.voice_config.asr()))


@router.put("/voice/asr")
async def update_asr_config(
    payload: AsrConfigRequest,
    request: Request,
) -> Response:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    await infrastructure.voice_config.update_asr(payload)
    return result_response(Result.ok())


@router.get("/voice/tts")
async def get_tts_config(request: Request) -> Response:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    return result_response(Result.ok(await infrastructure.voice_config.tts()))


@router.put("/voice/tts")
async def update_tts_config(
    payload: TtsConfigRequest,
    request: Request,
) -> Response:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    await infrastructure.voice_config.update_tts(payload)
    return result_response(Result.ok())


@router.post("/voice/asr/test")
async def test_asr_config(request: Request) -> Response:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    return result_response(Result.ok(await infrastructure.voice_config.test_asr()))


@router.post("/reload")
async def reload_providers(service: ServiceDependency) -> Response:
    await service.reload()
    return result_response(Result.ok())


@router.post("/models/discover")
async def discover_provider_models(
    payload: ModelDiscoveryRequest,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.discover_models(payload)))


@router.post("")
async def create_provider(
    payload: CreateProviderRequest,
    service: ServiceDependency,
) -> Response:
    await service.create(payload)
    return result_response(Result.ok(), status_code=201)


@router.get("/default-provider")
async def get_default_provider(service: ServiceDependency) -> Response:
    return result_response(Result.ok(await service.defaults()))


@router.put("/default-provider")
async def update_default_provider(
    payload: DefaultProviderRequest,
    service: ServiceDependency,
) -> Response:
    await service.update_default_chat(payload)
    return result_response(Result.ok())


@router.put("/default-embedding-provider")
async def update_default_embedding_provider(
    payload: DefaultProviderRequest,
    service: ServiceDependency,
) -> Response:
    await service.update_default_embedding(payload)
    return result_response(Result.ok())


@router.get("/{provider_id}")
async def get_provider(
    provider_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.get(provider_id)))


@router.post("/{provider_id}/test")
async def test_provider(
    provider_id: str,
    service: ServiceDependency,
) -> Response:
    return result_response(Result.ok(await service.test(provider_id)))


@router.put("/{provider_id}")
async def update_provider(
    provider_id: str,
    payload: UpdateProviderRequest,
    service: ServiceDependency,
) -> Response:
    await service.update(provider_id, payload)
    return result_response(Result.ok())


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: str,
    service: ServiceDependency,
) -> Response:
    await service.delete(provider_id)
    return result_response(Result.ok())
