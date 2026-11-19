#!/usr/bin/env python3
"""Create a demo account and send a few synthetic medical emails.

Usage:
    python scripts/seed_demo.py
    python scripts/seed_demo.py --email demo@example.com --password password123
"""

from __future__ import annotations

import argparse
import smtplib
import uuid
from email.message import EmailMessage

import httpx

BASE_URL = "http://127.0.0.1:8000"
SMTP_HOST = "127.0.0.1"
SMTP_PORT = 8025

MESSAGES = [
    {
        "subject": "Результаты общего анализа крови",
        "filename": "blood-test.pdf",
        "sender": "Лаборатория Инвитро <results@invitro.example>",
        "body": "Добрый день! Во вложении результаты общего анализа крови.",
        "pdf": b"%PDF-1.4\n% synthetic blood test\n%%EOF\n",
    },
    {
        "subject": "Заключение кардиолога",
        "filename": "cardiologist-report.pdf",
        "sender": "Клиника Сердце <doctor@cardio.example>",
        "body": "Направляю заключение по итогам приёма.",
        "pdf": b"%PDF-1.4\n% synthetic cardiologist report\n%%EOF\n",
    },
    {
        "subject": "Запись на приём 25 ноября",
        "filename": "appointment.pdf",
        "sender": "Поликлиника 12 <registry@clinic.example>",
        "body": "Подтверждение записи на приём.",
        "pdf": b"%PDF-1.4\n% synthetic appointment\n%%EOF\n",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="demo@example.com")
    parser.add_argument("--password", default="password123")
    args = parser.parse_args()

    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        registered = client.post(
            "/v1/auth/register",
            json={"email": args.email, "password": args.password},
        )
        if registered.status_code == 201:
            payload = registered.json()
        elif registered.status_code == 409:
            login = client.post(
                "/v1/auth/login",
                json={"email": args.email, "password": args.password},
            )
            login.raise_for_status()
            payload = login.json()
        else:
            registered.raise_for_status()
            return

        token = payload["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        account = client.post("/v1/mail/accounts", headers=headers)
        account.raise_for_status()
        address = account.json()["address"]

        for item in MESSAGES:
            message = EmailMessage()
            message["From"] = item["sender"]
            message["To"] = address
            message["Subject"] = item["subject"]
            message["Message-ID"] = f"<demo-{uuid.uuid4().hex}@example.com>"
            message.set_content(item["body"])
            message.add_attachment(
                item["pdf"],
                maintype="application",
                subtype="pdf",
                filename=item["filename"],
            )
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
                smtp.send_message(message)

        inbox = client.get("/v1/inbox", headers=headers)
        inbox.raise_for_status()

    print(f"email:    {args.email}")
    print(f"password: {args.password}")
    print(f"address:  {address}")
    print(f"token:    {token}")
    print(f"inbox:    {len(inbox.json())} item(s)")


if __name__ == "__main__":
    main()
