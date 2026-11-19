from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt_secret
from app.core.security import utcnow
from app.models import MailAccount
from app.services.mail_ingest import ingest_raw_message
from app.services.storage import Storage

_FETCH_RE = re.compile(rb"^\d+ FETCH \(")
_UID_LIST_RE = re.compile(rb"^[\d ]+$")


class ImapError(RuntimeError):
    """Raised when the IMAP server cannot be reached or rejects the login."""


@dataclass(frozen=True)
class ImapCredentials:
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool
    folder: str


@dataclass
class ImapSyncStats:
    fetched: int = 0
    accepted: int = 0
    duplicates: int = 0
    skipped: int = 0
    inbox_items: int = 0
    last_uid: int = 0


class ImapConnection(Protocol):
    async def search_uids(self, after_uid: int) -> list[int]: ...

    async def fetch_raw(self, uid: int) -> bytes | None: ...

    async def close(self) -> None: ...


def credentials_for(account: MailAccount) -> ImapCredentials:
    if not account.imap_host or not account.imap_username or not account.imap_password_enc:
        raise ImapError("imap_account_incomplete")
    try:
        password = decrypt_secret(account.imap_password_enc)
    except ValueError as exc:
        raise ImapError("imap_credentials_unreadable") from exc
    return ImapCredentials(
        host=account.imap_host,
        port=account.imap_port or (993 if account.imap_use_ssl else 143),
        username=account.imap_username,
        password=password,
        use_ssl=account.imap_use_ssl,
        folder=account.imap_folder or "INBOX",
    )


def _parse_uids(lines: list[bytes]) -> list[int]:
    uids: set[int] = set()
    for line in lines:
        if not isinstance(line, (bytes, bytearray)):
            continue
        text = bytes(line).strip()
        if not text or not _UID_LIST_RE.match(text):
            continue
        for chunk in text.split():
            uids.add(int(chunk))
    return sorted(uids)


def _extract_raw(lines: list[bytes]) -> bytes | None:
    for index, line in enumerate(lines):
        if isinstance(line, (bytes, bytearray)) and _FETCH_RE.match(bytes(line)):
            for candidate in lines[index + 1 :]:
                if isinstance(candidate, (bytes, bytearray)) and bytes(candidate):
                    return bytes(candidate)
            return None
    return None


class AioimaplibConnection:
    def __init__(self, client: object) -> None:
        self._client = client

    async def search_uids(self, after_uid: int) -> list[int]:
        try:
            response = await self._client.uid_search(
                "UID",
                f"{after_uid + 1}:*",
                charset=None,
            )
        except Exception as exc:  # noqa: BLE001 - network and protocol errors
            raise ImapError("imap_search_failed") from exc
        if response.result != "OK":
            raise ImapError("imap_search_failed")
        return [uid for uid in _parse_uids(response.lines) if uid > after_uid]

    async def fetch_raw(self, uid: int) -> bytes | None:
        try:
            response = await self._client.uid("fetch", str(uid), "(BODY.PEEK[])")
        except Exception as exc:  # noqa: BLE001 - network and protocol errors
            raise ImapError("imap_fetch_failed") from exc
        if response.result != "OK":
            return None
        return _extract_raw(response.lines)

    async def close(self) -> None:
        try:
            await self._client.logout()
        except Exception:  # noqa: BLE001 - logout failure must not mask sync errors
            pass


async def open_client(credentials: ImapCredentials) -> ImapConnection:
    import aioimaplib

    client_class = aioimaplib.IMAP4_SSL if credentials.use_ssl else aioimaplib.IMAP4
    client = client_class(
        credentials.host,
        credentials.port,
        timeout=settings.imap_timeout_seconds,
    )
    try:
        await client.wait_hello_from_server()
        login = await client.login(credentials.username, credentials.password)
        if login.result != "OK":
            raise ImapError("imap_login_failed")
        selected = await client.select(credentials.folder)
        if selected.result != "OK":
            raise ImapError("imap_select_failed")
    except ImapError:
        raise
    except Exception as exc:  # noqa: BLE001 - network and protocol errors
        raise ImapError("imap_connection_failed") from exc
    return AioimaplibConnection(client)


async def run_imap_sync(
    session: AsyncSession,
    storage: Storage,
    account: MailAccount,
    *,
    limit: int | None = None,
) -> ImapSyncStats:
    credentials = credentials_for(account)
    max_messages = limit if limit is not None else settings.imap_sync_limit
    stats = ImapSyncStats(last_uid=account.imap_last_uid)

    connection = await open_client(credentials)
    try:
        uids = await connection.search_uids(account.imap_last_uid)
        for uid in uids[:max_messages]:
            stats.fetched += 1
            raw = await connection.fetch_raw(uid)
            if raw:
                result = await ingest_raw_message(session, storage, raw, account.address)
                if result.status == "accepted":
                    stats.accepted += 1
                    stats.inbox_items += result.inbox_items
                elif result.status == "duplicate":
                    stats.duplicates += 1
                else:
                    stats.skipped += 1
            if uid > account.imap_last_uid:
                account.imap_last_uid = uid
                stats.last_uid = uid
    finally:
        await connection.close()

    account.last_sync_at = utcnow()
    await session.commit()
    return stats
