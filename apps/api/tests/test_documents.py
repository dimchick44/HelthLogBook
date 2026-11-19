from __future__ import annotations

import json

from tests.conftest import auth_headers, register_user

PDF = b"%PDF-1.4\nsynthetic document\n%%EOF\n"


async def test_upload_with_extraction(client):
    data = await register_user(client)
    headers = auth_headers(data["access_token"])
    extraction = {
        "document_type": "lab_result",
        "document_date": "2026-03-14",
        "confidence": 0.86,
    }

    response = await client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("analysis.pdf", PDF, "application/pdf")},
        data={
            "source": "mail",
            "source_ref": "message-1",
            "extraction": json.dumps(extraction),
        },
    )

    assert response.status_code == 201, response.text
    document = response.json()
    assert document["type"] == "lab_result"
    assert document["source"] == "mail"
    assert document["confidence"] == 0.86
    assert document["document_date"].startswith("2026-03-14")

    listing = await client.get("/v1/documents", headers=headers)
    assert len(listing.json()) == 1


async def test_duplicate_upload_returns_existing(client):
    data = await register_user(client)
    headers = auth_headers(data["access_token"])

    first = await client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("a.pdf", PDF, "application/pdf")},
    )
    second = await client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("a-copy.pdf", PDF, "application/pdf")},
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


async def test_documents_are_private(client):
    data = await register_user(client)
    headers = auth_headers(data["access_token"])
    created = await client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("a.pdf", PDF, "application/pdf")},
    )
    document_id = created.json()["id"]

    other = await register_user(client, email="other@example.com")
    other_headers = auth_headers(other["access_token"])

    response = await client.get(f"/v1/documents/{document_id}", headers=other_headers)
    assert response.status_code == 404


async def test_delete_document(client):
    data = await register_user(client)
    headers = auth_headers(data["access_token"])
    created = await client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("a.pdf", PDF, "application/pdf")},
    )
    document_id = created.json()["id"]

    deleted = await client.delete(f"/v1/documents/{document_id}", headers=headers)
    assert deleted.status_code == 204

    missing = await client.get(f"/v1/documents/{document_id}", headers=headers)
    assert missing.status_code == 404
