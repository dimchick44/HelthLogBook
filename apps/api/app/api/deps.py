from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db import get_session
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def unauthorized(message: str = "authentication_required") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "unauthorized", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def not_found(message: str = "not_found") -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "not_found", "message": message},
    )


def conflict(message: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": "conflict", "message": message},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise unauthorized()
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise unauthorized("invalid_token")
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise unauthorized("user_not_found")
    return user
