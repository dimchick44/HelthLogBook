from __future__ import annotations

from app.services.mail_ingest import ingest_raw_message
from tests.conftest import auth_headers, build_email, register_user


async def _prepare_item(client, session_factory, storage):
    data = await register_user(client)
    headers = auth_headers(data["access_token"])
    account = await client.post("/v1/mail/accounts", headers=headers)
    address = account.json()["address"]

    async with session_factory() as session:
        await ingest_raw_message(session, storage, build_email(recipient=address), address)

    inbox = await client.get("/v1/inbox", headers=headers)
    return data, headers, inbox.json()[0]


async def test_claim_and_complete_flow(client, session_factory, storage):
    _, headers, item = await _prepare_item(client, session_factory, storage)
    item_id = item["id"]

    downloaded = await client.get(f"/v1/inbox/{item_id}/file", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF-")

    claimed = await client.post(
        f"/v1/inbox/{item_id}/claim",
        json={"device_id": "device-1"},
        headers=headers,
    )
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "claimed"

    same_device = await client.post(
        f"/v1/inbox/{item_id}/claim",
        json={"device_id": "device-1"},
        headers=headers,
    )
    assert same_device.status_code == 200

    other_device = await client.post(
        f"/v1/inbox/{item_id}/claim",
        json={"device_id": "device-2"},
        headers=headers,
    )
    assert other_device.status_code == 409

    completed = await client.post(
        f"/v1/inbox/{item_id}/complete",
        json={"status": "done", "device_id": "device-1"},
        headers=headers,
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "done"

    pending = await client.get("/v1/inbox?status=pending", headers=headers)
    assert pending.json() == []


async def test_inbox_is_private(client, session_factory, storage):
    _, _, item = await _prepare_item(client, session_factory, storage)
    other = await register_user(client, email="other@example.com")
    headers = auth_headers(other["access_token"])

    response = await client.get(f"/v1/inbox/{item['id']}", headers=headers)
    assert response.status_code == 404

    download = await client.get(f"/v1/inbox/{item['id']}/file", headers=headers)
    assert download.status_code == 404


async def test_inbox_requires_auth(client):
    response = await client.get("/v1/inbox")
    assert response.status_code == 401
