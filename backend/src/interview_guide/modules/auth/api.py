from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse, Response

from interview_guide.common.api.responses import STANDARD_ERROR_RESPONSES
from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.infrastructure import RuntimeInfrastructure
from interview_guide.modules.auth.dependencies import current_actor, current_session
from interview_guide.modules.auth.domain import Actor
from interview_guide.modules.auth.middleware import request_origin_allowed
from interview_guide.modules.auth.models import (
    AuthSessionResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
)
from interview_guide.modules.auth.service import AuthenticatedSession, AuthService
from interview_guide.modules.auth.session import AuthSession

router = APIRouter(prefix="/api/auth", responses=STANDARD_ERROR_RESPONSES)


def auth_service(request: Request) -> AuthService:
    infrastructure: RuntimeInfrastructure = request.app.state.infrastructure
    return infrastructure.auth_runtime.service


ServiceDependency = Annotated[AuthService, Depends(auth_service)]
ActorDependency = Annotated[Actor, Depends(current_actor)]
SessionDependency = Annotated[AuthSession, Depends(current_session)]


@router.post("/register", response_model=AuthSessionResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    service: ServiceDependency,
) -> Response:
    require_public_origin(request)
    authenticated = await service.register(payload, client_ip=client_ip(request))
    return session_response(authenticated, request.app.state.settings, status_code=201)


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    service: ServiceDependency,
) -> Response:
    require_public_origin(request)
    authenticated = await service.login(payload, client_ip=client_ip(request))
    return session_response(authenticated, request.app.state.settings)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    service: ServiceDependency,
    actor: ActorDependency,
) -> Response:
    await service.logout(actor)
    response = Response(status_code=204)
    clear_session_cookie(response, request.app.state.settings)
    return response


@router.get("/me", response_model=AuthSessionResponse)
async def me(
    service: ServiceDependency,
    actor: ActorDependency,
    session: SessionDependency,
) -> AuthSessionResponse:
    return await service.current_session(actor, session)


@router.post("/password/change", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    service: ServiceDependency,
    actor: ActorDependency,
) -> Response:
    await service.change_password(actor, payload)
    response = Response(status_code=204)
    clear_session_cookie(response, request.app.state.settings)
    return response


@router.post("/sessions/revoke", status_code=204)
async def revoke_sessions(
    request: Request,
    service: ServiceDependency,
    actor: ActorDependency,
) -> Response:
    await service.revoke_all(actor)
    response = Response(status_code=204)
    clear_session_cookie(response, request.app.state.settings)
    return response


def session_response(
    authenticated: AuthenticatedSession,
    settings: Settings,
    *,
    status_code: int = 200,
) -> JSONResponse:
    response = JSONResponse(
        content=jsonable_encoder(authenticated.response),
        status_code=status_code,
    )
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=authenticated.created.token,
        max_age=settings.auth_session_absolute_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"


def require_public_origin(request: Request) -> None:
    if not request_origin_allowed(request.headers, request.scope, request.app.state.settings):
        raise BusinessException(ErrorCode.AUTH_CSRF_INVALID)


def client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"
