from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, not_found
from app.core.config import settings
from app.db import get_session
from app.models import Document, DocumentFile, User
from app.schemas import DocumentOut
from app.services.mail_parser import suffix_for
from app.services.storage import Storage, get_storage_dep

router = APIRouter(prefix="/documents", tags=["documents"])

DOCUMENT_TYPES = {
    "lab_result",
    "doctor_visit",
    "imaging_report",
    "prescription",
    "discharge_summary",
    "vaccination",
    "referral",
    "invoice",
    "other",
    "unknown",
}


def _parse_extraction(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    response: Response,
    file: UploadFile = File(...),
    source: str = Form(default="upload"),
    source_ref: str | None = Form(default=None),
    extraction: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage_dep),
) -> Document:
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_file", "message": "file_is_empty"},
        )
    if len(data) > settings.max_attachment_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "file_too_large", "message": "file_exceeds_limit"},
        )

    digest = sha256(data).hexdigest()
    existing = await session.scalar(
        select(Document).where(
            Document.user_id == user.id,
            Document.content_hash == digest,
        )
    )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return existing

    payload = _parse_extraction(extraction)
    doc_type = payload.get("document_type")
    if doc_type not in DOCUMENT_TYPES:
        doc_type = "unknown"

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = None
    else:
        confidence = float(confidence)

    mime = file.content_type or "application/octet-stream"
    filename = file.filename or f"document{suffix_for(mime, '')}"
    key = f"users/{user.id}/documents/{digest}{suffix_for(mime, filename)}"
    await storage.put(key, data)

    document = Document(
        user_id=user.id,
        type=doc_type,
        status="ready",
        source=source[:16],
        source_ref=source_ref[:128] if source_ref else None,
        document_date=_parse_date(payload.get("document_date")),
        confidence=confidence,
        content_hash=digest,
        extraction_json=json.dumps(payload, ensure_ascii=False) if payload else None,
    )
    session.add(document)
    await session.flush()
    session.add(
        DocumentFile(
            document_id=document.id,
            storage_key=key,
            mime=mime,
            size=len(data),
            sha256=digest,
        )
    )
    await session.commit()
    await session.refresh(document)
    return document


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Document]:
    result = await session.scalars(
        select(Document)
        .where(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
        .limit(limit)
    )
    return list(result)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Document:
    document = await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user.id,
        )
    )
    if document is None:
        raise not_found("document_not_found")
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage_dep),
) -> Response:
    document = await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user.id,
        )
    )
    if document is None:
        raise not_found("document_not_found")

    files = await session.scalars(
        select(DocumentFile).where(DocumentFile.document_id == document.id)
    )
    for document_file in files:
        await storage.delete(document_file.storage_key)

    await session.delete(document)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
