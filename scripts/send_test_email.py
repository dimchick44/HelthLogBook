#!/usr/bin/env python3
"""Send a synthetic medical email to the local SMTP receiver.

Usage:
    python scripts/send_test_email.py --to u-<token>@in.medarchive.local
"""

from __future__ import annotations

import argparse
import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path

SYNTHETIC_PDF = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj
trailer << /Root 1 0 R >>
%%EOF
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True, help="recipient forwarding address")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8025)
    parser.add_argument("--subject", default="Результаты анализов")
    parser.add_argument("--attachment", type=Path, default=None)
    parser.add_argument("--message-id", default="<synthetic-test@example.com>")
    args = parser.parse_args()

    message = EmailMessage()
    message["From"] = "Лаборатория <lab@example.com>"
    message["To"] = args.to
    message["Subject"] = args.subject
    message["Message-ID"] = args.message_id
    message.set_content("Результаты исследования во вложении.")

    if args.attachment:
        data = args.attachment.read_bytes()
        mime, _ = mimetypes.guess_type(args.attachment.name)
        maintype, subtype = (mime or "application/octet-stream").split("/", 1)
        message.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype,
            filename=args.attachment.name,
        )
    else:
        message.add_attachment(
            SYNTHETIC_PDF,
            maintype="application",
            subtype="pdf",
            filename="synthetic-results.pdf",
        )

    with smtplib.SMTP(args.host, args.port, timeout=15) as smtp:
        smtp.send_message(message)
    print(f"sent to {args.to} via {args.host}:{args.port}")


if __name__ == "__main__":
    main()
