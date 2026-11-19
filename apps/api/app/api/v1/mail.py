from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, not_found
from app.core.config import settings
from app.core.crypto import encrypt_secret
from app.core.security import utcnow
from app.db import get_session
from app.models import MailAccount, MailRule, User
from app.schemas import (
    ImapAccountIn,
    MailAccountOut,
    MailRuleIn,
    MailRuleOut,
    MailSyncResult,
)
from app.services.imap_sync import ImapError, run_imap_sync
from app.services.storage import Storage, get_storage_dep

router = APIRouter(prefix="/mail", tags=["mail"])


async def get_owned_account(
    session: AsyncSession,
    user: User,
    account_id: str,
) -> MailAccount:
    account = await session.scalar(
        select(MailAccount).where(
            MailAccount.id == account_id,
            MailAccount.user_id == user.id,
        )
    )
    if account is None:
        raise not_found("mail_account_not_found")
    return account


@router.post("/accounts", response_model=MailAccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MailAccount:
    existing = await session.scalar(
        select(MailAccount).where(
            MailAccount.user_id == user.id,
            MailAccount.kind == "forward",
            MailAccount.status == "active",
        )
    )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return existing

    token = secrets.token_hex(12)
    account = MailAccount(
        user_id=user.id,
        kind="forward",
        address=f"u-{token}@{settings.mail_domain}",
        token=token,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


@router.post(
    "/accounts/imap",
    response_model=MailAccountOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_imap_account(
    payload: ImapAccountIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MailAccount:
    address = str(payload.address).lower()
    existing = await session.scalar(
        select(MailAccount).where(MailAccount.address == address)
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "mail_address_taken",
                "message": "mail_address_already_connected",
            },
        )

    account = MailAccount(
        user_id=user.id,
        kind="imap",
        address=address,
        token=secrets.token_hex(12),
        imap_host=payload.host,
        imap_port=payload.port,
        imap_username=payload.username,
        imap_password_enc=encrypt_secret(payload.password),
        imap_use_ssl=payload.use_ssl,
        imap_folder=payload.folder,
    )
    session.add(account)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "mail_address_taken",
                "message": "mail_address_already_connected",
            },
        ) from None
    await session.refresh(account)
    return account


@router.get("/accounts", response_model=list[MailAccountOut])
async def list_accounts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MailAccount]:
    result = await session.scalars(
        select(MailAccount)
        .where(MailAccount.user_id == user.id)
        .order_by(MailAccount.created_at.desc())
    )
    return list(result)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_account(
    account_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    account = await get_owned_account(session, user, account_id)
    account.status = "disabled"
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/accounts/{account_id}/sync", response_model=MailSyncResult)
async def sync_account(
    account_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage_dep),
) -> MailSyncResult:
    account = await get_owned_account(session, user, account_id)
    if account.status != "active":
        raise HTTPException(
            status_code=409,
            detail={"code": "account_disabled", "message": "mail_account_disabled"},
        )

    if account.kind != "imap":
        account.last_sync_at = utcnow()
        await session.commit()
        await session.refresh(account)
        return MailSyncResult(
            account_id=account.id,
            kind=account.kind,
            last_sync_at=account.last_sync_at,
        )

    try:
        stats = await run_imap_sync(session, storage, account)
    except ImapError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": str(exc), "message": "imap_sync_failed"},
        ) from exc

    return MailSyncResult(
        account_id=account.id,
        kind=account.kind,
        fetched=stats.fetched,
        accepted=stats.accepted,
        duplicates=stats.duplicates,
        skipped=stats.skipped,
        inbox_items=stats.inbox_items,
        last_uid=stats.last_uid,
        last_sync_at=account.last_sync_at,
    )


@router.get("/accounts/{account_id}/rules", response_model=list[MailRuleOut])
async def list_rules(
    account_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MailRule]:
    account = await get_owned_account(session, user, account_id)
    result = await session.scalars(
        select(MailRule)
        .where(MailRule.account_id == account.id)
        .order_by(MailRule.created_at)
    )
    return list(result)


@router.post(
    "/accounts/{account_id}/rules",
    response_model=MailRuleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_rule(
    account_id: str,
    payload: MailRuleIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MailRule:
    account = await get_owned_account(session, user, account_id)
    value = payload.value.strip().lower()
    if not value:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_rule", "message": "rule_value_is_empty"},
        )
    if payload.kind == "mime" and "/" not in value:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_rule", "message": "mime_rule_requires_slash"},
        )

    rule = MailRule(
        account_id=account.id,
        user_id=user.id,
        kind=payload.kind,
        value=value,
        action=payload.action,
        enabled=payload.enabled,
    )
    session.add(rule)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "rule_exists", "message": "mail_rule_already_exists"},
        ) from None
    await session.refresh(rule)
    return rule


@router.delete(
    "/accounts/{account_id}/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_rule(
    account_id: str,
    rule_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    account = await get_owned_account(session, user, account_id)
    rule = await session.scalar(
        select(MailRule).where(
            MailRule.id == rule_id,
            MailRule.account_id == account.id,
        )
    )
    if rule is None:
        raise not_found("mail_rule_not_found")
    await session.delete(rule)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
