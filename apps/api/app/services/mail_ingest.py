from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InboxItem, MailAccount, MailMessage, MailRule
from app.services.mail_filters import evaluate_rules
from app.services.mail_parser import parse_message, suffix_for
from app.services.storage import Storage


@dataclass
class IngestResult:
    status: str
    account_id: str | None = None
    message_id: str | None = None
    inbox_items: int = 0
    reason: str | None = None


async def ingest_raw_message(
    session: AsyncSession,
    storage: Storage,
    raw: bytes,
    recipient: str,
) -> IngestResult:
    address = recipient.strip().lower()
    account = await session.scalar(
        select(MailAccount).where(MailAccount.address == address)
    )
    if account is None or account.status != "active":
        return IngestResult(status="unknown_recipient", reason="account_not_found")

    parsed = parse_message(raw)
    dedupe_key = parsed.message_id or sha256(raw).hexdigest()

    existing = await session.scalar(
        select(MailMessage.id).where(
            MailMessage.account_id == account.id,
            MailMessage.dedupe_key == dedupe_key,
        )
    )
    if existing is not None:
        return IngestResult(
            status="duplicate",
            account_id=account.id,
            message_id=existing,
            reason="already_ingested",
        )

    rules = list(
        await session.scalars(
            select(MailRule).where(MailRule.account_id == account.id)
        )
    )
    decision = evaluate_rules(parsed, rules)
    if not decision.accepted:
        message = MailMessage(
            account_id=account.id,
            user_id=account.user_id,
            message_id=parsed.message_id,
            subject=parsed.subject,
            sender=parsed.sender,
            received_at=parsed.received_at,
            dedupe_key=dedupe_key,
            status="skipped",
            skip_reason=decision.reason,
            attachment_count=0,
        )
        session.add(message)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            return IngestResult(
                status="duplicate",
                account_id=account.id,
                reason="already_ingested",
            )
        await session.commit()
        return IngestResult(
            status="skipped",
            account_id=account.id,
            message_id=message.id,
            inbox_items=0,
            reason=decision.reason,
        )

    message = MailMessage(
        account_id=account.id,
        user_id=account.user_id,
        message_id=parsed.message_id,
        subject=parsed.subject,
        sender=parsed.sender,
        received_at=parsed.received_at,
        dedupe_key=dedupe_key,
        status="processed" if parsed.attachments else "skipped",
        skip_reason=parsed.skipped_reason,
        attachment_count=len(parsed.attachments),
    )
    session.add(message)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return IngestResult(
            status="duplicate",
            account_id=account.id,
            reason="already_ingested",
        )

    created = 0
    for attachment in parsed.attachments:
        key = (
            f"users/{account.user_id}/mail/{message.id}/"
            f"{attachment.sha256}{suffix_for(attachment.mime, attachment.filename)}"
        )
        await storage.put(key, attachment.data)
        session.add(
            InboxItem(
                user_id=account.user_id,
                mail_message_id=message.id,
                filename=attachment.filename,
                mime=attachment.mime,
                size=attachment.size,
                sha256=attachment.sha256,
                storage_key=key,
            )
        )
        created += 1

    await session.commit()
    return IngestResult(
        status="accepted",
        account_id=account.id,
        message_id=message.id,
        inbox_items=created,
        reason=parsed.skipped_reason,
    )
