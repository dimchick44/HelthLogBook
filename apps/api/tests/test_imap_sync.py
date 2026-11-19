from __future__ import annotations

from sqlalchemy import select

from app.core.crypto import decrypt_secret, encrypt_secret
from app.models import MailAccount
from app.services import imap_sync
from app.services.imap_sync import ImapError
from tests.conftest import auth_headers, build_email, register_user

IMAP_PAYLOAD = {
    "address": "user@example.com",
    "host": "imap.example.com",
    "port": 993,
    "username": "user@example.com",
    "password": "app-password",
    "use_ssl": True,
    "folder": "INBOX",
}


class FakeConnection:
    def __init__(self, messages: dict[int, bytes]) -> None:
        self.messages = messages
        self.closed = False

    async def search_uids(self, after_uid: int) -> list[int]:
        return sorted(uid for uid in self.messages if uid > after_uid)

    async def fetch_raw(self, uid: int) -> bytes | None:
        return self.messages.get(uid)

    async def close(self) -> None:
        self.closed = True


def install_fake(monkeypatch, messages: dict[int, bytes]) -> FakeConnection:
    connection = FakeConnection(messages)

    async def fake_open(credentials):
        assert credentials.host == "imap.example.com"
        assert credentials.username == "user@example.com"
        assert credentials.password == "app-password"
        return connection

    monkeypatch.setattr(imap_sync, "open_client", fake_open)
    return connection


async def _register(client, email: str = "user@example.com") -> dict:
    data = await register_user(client, email=email)
    return auth_headers(data["access_token"])


async def _create_imap(client, headers, address: str = "user@example.com") -> dict:
    payload = dict(IMAP_PAYLOAD, address=address)
    response = await client.post("/v1/mail/accounts/imap", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_secret_encryption_roundtrip():
    token = encrypt_secret("app-password")
    assert token != "app-password"
    assert decrypt_secret(token) == "app-password"


class FakeLowLevelClient:
    def __init__(self, search_lines, fetch_lines=None) -> None:
        self.search_lines = search_lines
        self.fetch_lines = fetch_lines or []
        self.search_args = None
        self.logged_out = False

    async def uid_search(self, *criteria, charset=None):
        self.search_args = (criteria, charset)
        return _response("OK", self.search_lines)

    async def uid(self, command, *criteria):
        return _response("OK", self.fetch_lines)

    async def logout(self) -> None:
        self.logged_out = True


def _response(result, lines):
    from types import SimpleNamespace

    return SimpleNamespace(result=result, lines=lines)


async def test_aioimaplib_connection_parses_responses():
    from app.services.imap_sync import AioimaplibConnection

    low_level = FakeLowLevelClient(
        search_lines=[b"1 2 5", b"OK done"],
        fetch_lines=[
            b"5 FETCH (UID 5 BODY[] {24}",
            b"From: lab@example.com\r\n",
            b")",
        ],
    )
    connection = AioimaplibConnection(low_level)

    assert await connection.search_uids(2) == [5]
    assert low_level.search_args == (("UID", "3:*"), None)

    raw = await connection.fetch_raw(5)
    assert raw == b"From: lab@example.com\r\n"

    await connection.close()
    assert low_level.logged_out is True


async def test_create_imap_account_hides_password(client, session_factory):
    headers = await _register(client)
    account = await _create_imap(client, headers)

    assert account["kind"] == "imap"
    assert account["address"] == "user@example.com"
    assert account["imap_host"] == "imap.example.com"
    assert account["imap_last_uid"] == 0
    assert "password" not in account
    assert "imap_password_enc" not in account

    async with session_factory() as session:
        stored = await session.scalar(select(MailAccount).where(MailAccount.id == account["id"]))
    assert stored is not None
    assert stored.imap_password_enc != "app-password"
    assert decrypt_secret(stored.imap_password_enc) == "app-password"


async def test_imap_sync_ingests_new_messages(client, monkeypatch):
    headers = await _register(client)
    account = await _create_imap(client, headers)
    install_fake(
        monkeypatch,
        {
            1: build_email(recipient="user@example.com", message_id="<imap-1@example.com>"),
            2: build_email(
                recipient="user@example.com",
                message_id="<imap-2@example.com>",
                filename="second.pdf",
            ),
        },
    )

    first = await client.post(
        f"/v1/mail/accounts/{account['id']}/sync",
        headers=headers,
    )
    assert first.status_code == 200, first.text
    stats = first.json()
    assert stats["kind"] == "imap"
    assert stats["fetched"] == 2
    assert stats["accepted"] == 2
    assert stats["inbox_items"] == 2
    assert stats["last_uid"] == 2

    inbox = await client.get("/v1/inbox", headers=headers)
    assert len(inbox.json()) == 2

    second = await client.post(
        f"/v1/mail/accounts/{account['id']}/sync",
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["fetched"] == 0


async def test_imap_sync_deduplicates_same_message(client, monkeypatch):
    headers = await _register(client)
    account = await _create_imap(client, headers)
    raw = build_email(recipient="user@example.com", message_id="<same@example.com>")
    install_fake(monkeypatch, {1: raw, 2: raw})

    response = await client.post(f"/v1/mail/accounts/{account['id']}/sync", headers=headers)
    assert response.status_code == 200
    stats = response.json()
    assert stats["fetched"] == 2
    assert stats["accepted"] == 1
    assert stats["duplicates"] == 1
    assert stats["inbox_items"] == 1

    inbox = await client.get("/v1/inbox", headers=headers)
    assert len(inbox.json()) == 1


async def test_imap_sync_advances_uid_on_skip(client, monkeypatch):
    headers = await _register(client)
    account = await _create_imap(client, headers)
    rule = await client.post(
        f"/v1/mail/accounts/{account['id']}/rules",
        headers=headers,
        json={"kind": "keyword", "value": "анализ", "action": "deny"},
    )
    assert rule.status_code == 201, rule.text
    install_fake(
        monkeypatch,
        {
            5: build_email(
                recipient="user@example.com",
                message_id="<exe@example.com>",
                attachment=b"MZ\x90\x00not-a-document",
                filename="program.exe",
                maintype="application",
                subtype="octet-stream",
            )
        },
    )

    response = await client.post(f"/v1/mail/accounts/{account['id']}/sync", headers=headers)
    assert response.status_code == 200
    stats = response.json()
    assert stats["fetched"] == 1
    assert stats["skipped"] == 1
    assert stats["inbox_items"] == 0
    assert stats["last_uid"] == 5

    listed = await client.get("/v1/mail/accounts", headers=headers)
    synced = next(item for item in listed.json() if item["id"] == account["id"])
    assert synced["imap_last_uid"] == 5


async def test_imap_sync_connection_error(client, monkeypatch):
    headers = await _register(client)
    account = await _create_imap(client, headers)

    async def failing_open(credentials):
        raise ImapError("imap_login_failed")

    monkeypatch.setattr(imap_sync, "open_client", failing_open)

    response = await client.post(f"/v1/mail/accounts/{account['id']}/sync", headers=headers)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "imap_login_failed"


async def test_imap_account_is_private(client, monkeypatch):
    headers = await _register(client)
    account = await _create_imap(client, headers)
    install_fake(monkeypatch, {1: build_email(recipient="user@example.com")})

    other = await _register(client, email="other@example.com")
    response = await client.post(
        f"/v1/mail/accounts/{account['id']}/sync",
        headers=other,
    )
    assert response.status_code == 404


async def test_duplicate_imap_address_rejected(client):
    headers = await _register(client)
    await _create_imap(client, headers)

    other = await _register(client, email="other@example.com")
    response = await client.post("/v1/mail/accounts/imap", headers=other, json=IMAP_PAYLOAD)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "mail_address_taken"


async def test_unreadable_password_returns_502(client, session_factory):
    headers = await _register(client)
    account = await _create_imap(client, headers)

    async with session_factory() as session:
        stored = await session.get(MailAccount, account["id"])
        assert stored is not None
        stored.imap_password_enc = "not-a-fernet-token"
        await session.commit()

    response = await client.post(f"/v1/mail/accounts/{account['id']}/sync", headers=headers)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "imap_credentials_unreadable"


async def test_forward_account_sync_returns_empty_stats(client):
    headers = await _register(client)
    created = await client.post("/v1/mail/accounts", headers=headers)
    account = created.json()

    response = await client.post(f"/v1/mail/accounts/{account['id']}/sync", headers=headers)
    assert response.status_code == 200
    stats = response.json()
    assert stats["kind"] == "forward"
    assert stats["fetched"] == 0
    assert stats["last_sync_at"] is not None
