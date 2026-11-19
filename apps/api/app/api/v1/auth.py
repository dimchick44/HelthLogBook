from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, unauthorized
from app.core.config import settings
from app.core.security import (
    create_access_token,
    ensure_aware,
    hash_password,
    hash_token,
    new_refresh_token,
    refresh_expires_at,
    utcnow,
    verify_password,
)
from app.db import get_session
from app.models import RefreshToken, User
from app.schemas import AuthResponse, LoginIn, RefreshIn, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_tokens(session: AsyncSession, user: User) -> AuthResponse:
    raw_refresh, token_hash = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=refresh_expires_at(),
        )
    )
    await session.commit()
    return AuthResponse(
        user=UserOut.model_validate(user),
        access_token=create_access_token(user.id),
        refresh_token=raw_refresh,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterIn,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    email = payload.email.lower()
    existing = await session.scalar(select(User.id).where(User.email == email))
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "email_taken", "message": "email_already_registered"},
        )
    user = User(email=email, password_hash=hash_password(payload.password))
    session.add(user)
    await session.flush()
    return await _issue_tokens(session, user)


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginIn,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or user.deleted_at is not None:
        raise unauthorized("invalid_credentials")
    if not verify_password(payload.password, user.password_hash):
        raise unauthorized("invalid_credentials")
    return await _issue_tokens(session, user)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    payload: RefreshIn,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    token = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(payload.refresh_token),
            RefreshToken.revoked_at.is_(None),
        )
    )
    if token is None or ensure_aware(token.expires_at) <= utcnow():
        raise unauthorized("invalid_refresh_token")

    token.revoked_at = utcnow()
    user = await session.get(User, token.user_id)
    if user is None or user.deleted_at is not None:
        raise unauthorized("user_not_found")
    return await _issue_tokens(session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshIn,
    session: AsyncSession = Depends(get_session),
) -> Response:
    token = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(payload.refresh_token),
            RefreshToken.revoked_at.is_(None),
        )
    )
    if token is not None:
        token.revoked_at = utcnow()
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
