from __future__ import annotations

from starlette.requests import HTTPConnection

from interview_guide.common.db.models import LEGACY_OWNER_ID
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.modules.auth.domain import Actor, UserRole
from interview_guide.modules.auth.session import AuthSession


def current_actor(request: HTTPConnection) -> Actor:
    actor = getattr(request.state, "actor", None)
    if not isinstance(actor, Actor):
        settings = getattr(request.app.state, "settings", None)
        if settings is not None and not settings.auth_enabled:
            return Actor(
                user_id=LEGACY_OWNER_ID,
                role=UserRole.ADMIN,
                session_id="legacy-single-user",
                csrf_token="legacy-single-user",
            )
        raise BusinessException(ErrorCode.AUTH_SESSION_INVALID)
    return actor


def current_session(request: HTTPConnection) -> AuthSession:
    session = getattr(request.state, "auth_session", None)
    if not isinstance(session, AuthSession):
        raise BusinessException(ErrorCode.AUTH_SESSION_INVALID)
    return session
