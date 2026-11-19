#!/usr/bin/env python3
"""End-to-end smoke test for the mail pipeline.

Requires a running API (default http://127.0.0.1:8000) and SMTP receiver
(default 127.0.0.1:8025).

Creates a throwaway user, gets a forwarding address, sends a synthetic
email with a PDF attachment, then claims and completes the inbox item.
"""

from __future__ import annotations

import os
import smtplib
import time
import uuid
from email.message import EmailMessage

import httpx

BASE_URL = os.environ.get("MEDARCHIVE_BASE_URL", "http://127.0.0.1:8000")
SMTP_HOST = os.environ.get("MEDARCHIVE_SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.environ.get("MEDARCHIVE_SMTP_PORT", "8025"))

PDF = b"%PDF-1.4\nsynthetic smoke test\n%%EOF\n"


def main() -> None:
    email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"

    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        registered = client.post(
            "/v1/auth/register",
            json={"email": email, "password": password},
        )
        registered.raise_for_status()
        token = registered.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        account = client.post("/v1/mail/accounts", headers=headers)
        account.raise_for_status()
        address = account.json()["address"]

        message = EmailMessage()
        message["From"] = "Лаборатория <lab@example.com>"
        message["To"] = address
        message["Subject"] = "Результаты анализов (smoke)"
        message["Message-ID"] = f"<smoke-{uuid.uuid4().hex}@example.com>"
        message.set_content("Smoke test attachment.")
        message.add_attachment(
            PDF,
            maintype="application",
            subtype="pdf",
            filename="smoke-results.pdf",
        )

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            smtp.send_message(message)

        items = []
        for _ in range(40):
            response = client.get("/v1/inbox", headers=headers)
            response.raise_for_status()
            items = response.json()
            if items:
                break
            time.sleep(0.25)

        assert items, "inbox is still empty after SMTP delivery"
        item = items[0]
        assert item["filename"] == "smoke-results.pdf", item

        downloaded = client.get(f"/v1/inbox/{item['id']}/file", headers=headers)
        downloaded.raise_for_status()
        assert downloaded.content.startswith(b"%PDF-"), "attachment content mismatch"

        claimed = client.post(
            f"/v1/inbox/{item['id']}/claim",
            headers=headers,
            json={"device_id": "smoke-device"},
        )
        claimed.raise_for_status()
        assert claimed.json()["status"] == "claimed"

        completed = client.post(
            f"/v1/inbox/{item['id']}/complete",
            headers=headers,
            json={"status": "done", "device_id": "smoke-device"},
        )
        completed.raise_for_status()
        assert completed.json()["status"] == "done"

    print(f"SMOKE OK: {address} -> {item['filename']} ({item['size']} bytes)")


if __name__ == "__main__":
    main()
