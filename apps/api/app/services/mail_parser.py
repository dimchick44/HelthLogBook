from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from hashlib import sha256
from pathlib import Path

from app.core.config import settings

_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)

_SUFFIXES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/tiff": ".tiff",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
}


@dataclass(frozen=True)
class ParsedAttachment:
    filename: str
    mime: str
    data: bytes
    sha256: str
    size: int


@dataclass
class ParsedMessage:
    message_id: str | None
    subject: str
    sender: str
    received_at: datetime
    body_text: str = ""
    attachments: list[ParsedAttachment] = field(default_factory=list)
    skipped_reason: str | None = None


def sniff_mime(data: bytes) -> str | None:
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"):
            return "image/heic"
    return None


def suffix_for(mime: str, filename: str) -> str:
    if mime in _SUFFIXES:
        return _SUFFIXES[mime]
    suffix = Path(filename).suffix.lower()
    return suffix if suffix and len(suffix) <= 10 else ".bin"


def sanitize_filename(name: str | None, fallback: str) -> str:
    if not name:
        return fallback
    cleaned = name.replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned).strip()
    return cleaned[:255] or fallback


def _parse_date(value: str | None) -> datetime:
    if value:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc)


def parse_message(
    raw: bytes,
    *,
    max_bytes: int | None = None,
    allowed_mimes: tuple[str, ...] | None = None,
) -> ParsedMessage:
    max_bytes = max_bytes if max_bytes is not None else settings.max_attachment_bytes
    allowed = set(allowed_mimes or settings.allowed_attachment_mimes)

    message = BytesParser(policy=policy.default).parsebytes(raw)
    message_id = message.get("Message-ID")
    message_id = str(message_id).strip() if message_id else None

    parsed = ParsedMessage(
        message_id=message_id,
        subject=str(message.get("Subject", ""))[:998],
        sender=str(message.get("From", ""))[:998],
        received_at=_parse_date(message.get("Date")),
    )

    body_chunks: list[str] = []
    for part in message.walk():
        if part.get_content_type() != "text/plain":
            continue
        if part.get_content_disposition() == "attachment":
            continue
        try:
            content = part.get_content()
        except (LookupError, UnicodeDecodeError):
            continue
        if isinstance(content, str):
            body_chunks.append(content)
    parsed.body_text = "\n".join(body_chunks)[:5000]

    seen: set[str] = set()
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        if len(payload) > max_bytes:
            continue

        declared = part.get_content_type().lower()
        mime = declared
        if mime not in allowed:
            sniffed = sniff_mime(payload)
            if sniffed and sniffed in allowed:
                mime = sniffed
        if mime not in allowed:
            continue

        digest = sha256(payload).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)

        safe_name = sanitize_filename(filename, f"attachment{suffix_for(mime, filename)}")
        parsed.attachments.append(
            ParsedAttachment(
                filename=safe_name,
                mime=mime,
                data=payload,
                sha256=digest,
                size=len(payload),
            )
        )

    if not parsed.attachments:
        parsed.skipped_reason = "no_supported_attachments"
    return parsed
