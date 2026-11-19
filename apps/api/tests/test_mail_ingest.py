from __future__ import annotations

from app.services.mail_ingest import ingest_raw_message
from tests.conftest import auth_headers, build_email, register_user


async def _create_account(client, token: str) -> str:
    response = await client.post("/v1/mail/accounts", headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()["address"]


async def test_forward_account_created_once(client):
    data = await register_user(client)
    headers = auth_headers(data["access_token"])

    first = await client.post("/v1/mail/accounts", headers=headers)
    second = await client.post("/v1/mail/accounts", headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["address"].startswith("u-")
    assert first.json()["address"].endswith("@in.medarchive.local")


async def test_email_ingest_creates_inbox_item(client, session_factory, storage):
    data = await register_user(client)
    address = await _create_account(client, data["access_token"])
    raw = build_email(recipient=address)

    async with session_factory() as session:
        result = await ingest_raw_message(session, storage, raw, address)

    assert result.status == "accepted"
    assert result.inbox_items == 1

    inbox = await client.get(
        "/v1/inbox",
        headers=auth_headers(data["access_token"]),
    )
    assert inbox.status_code == 200
    items = inbox.json()
    assert len(items) == 1
    assert items[0]["filename"] == "results.pdf"
    assert items[0]["mime"] == "application/pdf"
    assert items[0]["status"] == "pending"


async def test_duplicate_email_is_ignored(client, session_factory, storage):
    data = await register_user(client)
    address = await _create_account(client, data["access_token"])
    raw = build_email(recipient=address)

    async with session_factory() as session:
        first = await ingest_raw_message(session, storage, raw, address)
    async with session_factory() as session:
        second = await ingest_raw_message(session, storage, raw, address)

    assert first.status == "accepted"
    assert second.status == "duplicate"

    inbox = await client.get("/v1/inbox", headers=auth_headers(data["access_token"]))
    assert len(inbox.json()) == 1


async def test_unknown_recipient_rejected(client, session_factory, storage):
    raw = build_email(recipient="u-unknown@in.medarchive.local")
    async with session_factory() as session:
        result = await ingest_raw_message(
            session,
            storage,
            raw,
            "u-unknown@in.medarchive.local",
        )
    assert result.status == "unknown_recipient"


async def test_unsupported_attachment_skipped(client, session_factory, storage):
    data = await register_user(client)
    address = await _create_account(client, data["access_token"])
    raw = build_email(
        recipient=address,
        attachment=b"MZ\x90\x00not-a-medical-file",
        filename="program.exe",
        maintype="application",
        subtype="octet-stream",
        message_id="<message-exe@example.com>",
    )

    async with session_factory() as session:
        result = await ingest_raw_message(session, storage, raw, address)

    assert result.status == "accepted"
    assert result.inbox_items == 0

    inbox = await client.get("/v1/inbox", headers=auth_headers(data["access_token"]))
    assert inbox.json() == []


async def test_octet_stream_pdf_is_sniffed(client, session_factory, storage):
    data = await register_user(client)
    address = await _create_account(client, data["access_token"])
    raw = build_email(
        recipient=address,
        attachment=b"%PDF-1.7\nsniffed pdf\n%%EOF\n",
        filename="scan.bin",
        maintype="application",
        subtype="octet-stream",
        message_id="<message-sniff@example.com>",
    )

    async with session_factory() as session:
        result = await ingest_raw_message(session, storage, raw, address)

    assert result.inbox_items == 1
