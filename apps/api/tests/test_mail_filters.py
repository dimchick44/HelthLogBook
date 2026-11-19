from __future__ import annotations

from app.services.mail_ingest import ingest_raw_message
from tests.conftest import auth_headers, build_email, register_user


async def _prepare(client):
    data = await register_user(client)
    headers = auth_headers(data["access_token"])
    account = await client.post("/v1/mail/accounts", headers=headers)
    assert account.status_code == 201
    payload = account.json()
    return data, headers, payload["id"], payload["address"]


async def _add_rule(client, headers, account_id, **rule):
    response = await client.post(
        f"/v1/mail/accounts/{account_id}/rules",
        headers=headers,
        json=rule,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_deny_keyword_skips_message(client, session_factory, storage):
    _, headers, account_id, address = await _prepare(client)
    await _add_rule(
        client,
        headers,
        account_id,
        kind="keyword",
        value="реклама",
        action="deny",
    )

    raw = build_email(
        recipient=address,
        subject="Реклама медицинских услуг",
        message_id="<ad-1@example.com>",
    )
    async with session_factory() as session:
        result = await ingest_raw_message(session, storage, raw, address)

    assert result.status == "skipped"
    assert result.reason == "denied_by_keyword"
    assert result.inbox_items == 0

    inbox = await client.get("/v1/inbox", headers=headers)
    assert inbox.json() == []


async def test_deny_domain_skips_message(client, session_factory, storage):
    _, headers, account_id, address = await _prepare(client)
    await _add_rule(
        client,
        headers,
        account_id,
        kind="domain",
        value="spam.example",
        action="deny",
    )

    raw = build_email(
        recipient=address,
        sender="Promo <promo@spam.example>",
        message_id="<spam-1@example.com>",
    )
    async with session_factory() as session:
        result = await ingest_raw_message(session, storage, raw, address)

    assert result.status == "skipped"
    assert result.reason == "denied_by_domain"


async def test_allow_list_requires_match(client, session_factory, storage):
    _, headers, account_id, address = await _prepare(client)
    await _add_rule(
        client,
        headers,
        account_id,
        kind="domain",
        value="lab.example",
        action="allow",
    )

    other = build_email(
        recipient=address,
        sender="Other <other@example.com>",
        message_id="<other-1@example.com>",
    )
    async with session_factory() as session:
        rejected = await ingest_raw_message(session, storage, other, address)
    assert rejected.status == "skipped"
    assert rejected.reason == "no_allow_rule_matched"

    allowed = build_email(
        recipient=address,
        sender="Lab <results@lab.example>",
        message_id="<lab-1@example.com>",
    )
    async with session_factory() as session:
        accepted = await ingest_raw_message(session, storage, allowed, address)
    assert accepted.status == "accepted"
    assert accepted.inbox_items == 1


async def test_mime_deny_skips_message(client, session_factory, storage):
    _, headers, account_id, address = await _prepare(client)
    await _add_rule(
        client,
        headers,
        account_id,
        kind="mime",
        value="application/pdf",
        action="deny",
    )

    raw = build_email(recipient=address, message_id="<pdf-1@example.com>")
    async with session_factory() as session:
        result = await ingest_raw_message(session, storage, raw, address)

    assert result.status == "skipped"
    assert result.reason == "denied_by_mime"


async def test_rule_crud_and_validation(client):
    _, headers, account_id, _ = await _prepare(client)
    base = f"/v1/mail/accounts/{account_id}/rules"

    created = await client.post(
        base,
        headers=headers,
        json={"kind": "domain", "value": "Clinic.Example", "action": "deny"},
    )
    assert created.status_code == 201
    rule = created.json()
    assert rule["value"] == "clinic.example"

    duplicate = await client.post(
        base,
        headers=headers,
        json={"kind": "domain", "value": "clinic.example", "action": "deny"},
    )
    assert duplicate.status_code == 409

    listed = await client.get(base, headers=headers)
    assert len(listed.json()) == 1

    invalid = await client.post(
        base,
        headers=headers,
        json={"kind": "mime", "value": "pdf", "action": "deny"},
    )
    assert invalid.status_code == 422

    deleted = await client.delete(f"{base}/{rule['id']}", headers=headers)
    assert deleted.status_code == 204

    empty = await client.get(base, headers=headers)
    assert empty.json() == []


async def test_rules_are_private(client):
    _, _, account_id, _ = await _prepare(client)
    other = await register_user(client, email="other@example.com")
    other_headers = auth_headers(other["access_token"])

    response = await client.get(
        f"/v1/mail/accounts/{account_id}/rules",
        headers=other_headers,
    )
    assert response.status_code == 404
