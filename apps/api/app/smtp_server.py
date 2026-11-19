from __future__ import annotations

import asyncio
import logging

from aiosmtpd.controller import Controller

from app.core.config import settings
from app.db import SessionLocal
from app.services.mail_ingest import ingest_raw_message
from app.services.storage import get_storage

logger = logging.getLogger("medarchive.smtp")


class MedicalMailHandler:
    async def handle_DATA(self, server, session, envelope) -> str:
        raw = envelope.content
        if isinstance(raw, str):
            raw = raw.encode("utf-8", errors="replace")

        results = []
        async with SessionLocal() as db:
            for recipient in envelope.rcpt_tos:
                try:
                    result = await ingest_raw_message(
                        db,
                        get_storage(),
                        raw,
                        recipient,
                    )
                    results.append(result)
                except Exception:
                    logger.exception("mail ingest failed for %s", recipient)
                    return "451 Requested action aborted: local error"

        accepted = [r for r in results if r.status in ("accepted", "duplicate", "skipped")]
        logger.info(
            "mail from=%s to=%s results=%s",
            envelope.mail_from,
            envelope.rcpt_tos,
            [(r.status, r.inbox_items) for r in results],
        )
        if not accepted:
            return "550 No such user here"
        return "250 Message accepted for delivery"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    controller = Controller(
        MedicalMailHandler(),
        hostname=settings.smtp_host,
        port=settings.smtp_port,
    )
    controller.start()
    logger.info("SMTP receiver listening on %s:%s", settings.smtp_host, settings.smtp_port)
    try:
        asyncio.run(asyncio.Event().wait())
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
