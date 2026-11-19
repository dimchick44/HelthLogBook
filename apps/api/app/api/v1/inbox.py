from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import conflict, get_current_user, not_found
from app.core.security import utcnow
from app.db import get_session
from app.models import Document, InboxItem, MailMessage, User
from app.schemas import ClaimIn, CompleteIn, InboxItemOut
from app.services.storage import Storage, get_storage_dep

router = APIRouter(prefix="/inbox", tags=["inbox"])


async def _get_item(
    session: AsyncSession,
    user: User,
    item_id: str,
) -> InboxItem:
    item = await session.scalar(
        select(InboxItem).where(
            InboxItem.id == item_id,
            InboxItem.user_id == user.id,
        )
    )
    if item is None:
        raise not_found("inbox_item_not_found")
    return item


def _to_out(item: InboxItem, message: MailMessage | None) -> InboxItemOut:
    return InboxItemOut(
        id=item.id,
        filename=item.filename,
        mime=item.mime,
        size=item.size,
        status=item.status,
        subject=message.subject if message else "",
        sender=message.sender if message else "",
        received_at=message.received_at if message else item.created_at,
        created_at=item.created_at,
        download_url=f"/v1/inbox/{item.id}/file",
    )


@router.get("", response_model=list[InboxItemOut])
async def list_inbox(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[InboxItemOut]:
    query = (
        select(InboxItem, MailMessage)
        .join(MailMessage, InboxItem.mail_message_id == MailMessage.id)
        .where(InboxItem.user_id == user.id)
        .order_by(InboxItem.created_at.desc())
        .limit(limit)
    )
    if status_filter:
        query = query.where(InboxItem.status == status_filter)
    rows = (await session.execute(query)).all()
    return [_to_out(item, message) for item, message in rows]


@router.get("/{item_id}", response_model=InboxItemOut)
async def get_inbox_item(
    item_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InboxItemOut:
    item = await _get_item(session, user, item_id)
    message = await session.get(MailMessage, item.mail_message_id)
    return _to_out(item, message)


@router.get("/{item_id}/file")
async def download_inbox_item(
    item_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage_dep),
) -> Response:
    item = await _get_item(session, user, item_id)
    data = await storage.get(item.storage_key)
    disposition = f"attachment; filename*=UTF-8''{quote(item.filename)}"
    return Response(
        content=data,
        media_type=item.mime,
        headers={"Content-Disposition": disposition},
    )


@router.post("/{item_id}/claim", response_model=InboxItemOut)
async def claim_item(
    item_id: str,
    payload: ClaimIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InboxItemOut:
    item = await _get_item(session, user, item_id)
    if item.status == "claimed":
        if item.claimed_by_device_id != payload.device_id:
            raise conflict("claimed_by_another_device")
    elif item.status != "pending":
        raise conflict("item_not_claimable")
    else:
        item.status = "claimed"
        item.claimed_by_device_id = payload.device_id
        item.claimed_at = utcnow()
        await session.commit()
        await session.refresh(item)

    message = await session.get(MailMessage, item.mail_message_id)
    return _to_out(item, message)


@router.post("/{item_id}/complete", response_model=InboxItemOut)
async def complete_item(
    item_id: str,
    payload: CompleteIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InboxItemOut:
    item = await _get_item(session, user, item_id)
    if item.status not in ("claimed", "pending"):
        raise conflict("item_not_completable")
    if item.claimed_by_device_id and payload.device_id:
        if item.claimed_by_device_id != payload.device_id:
            raise conflict("claimed_by_another_device")

    if payload.document_id:
        owned_document = await session.scalar(
            select(Document.id).where(
                Document.id == payload.document_id,
                Document.user_id == user.id,
            )
        )
        if owned_document is None:
            raise not_found("document_not_found")

    item.status = payload.status
    item.document_id = payload.document_id
    await session.commit()
    await session.refresh(item)

    message = await session.get(MailMessage, item.mail_message_id)
    return _to_out(item, message)
