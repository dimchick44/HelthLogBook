from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    locale: str
    created_at: datetime


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=512)


class AuthResponse(BaseModel):
    user: UserOut
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class MailAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    address: str
    status: str
    imap_host: str | None = None
    imap_port: int | None = None
    imap_username: str | None = None
    imap_use_ssl: bool = True
    imap_folder: str = "INBOX"
    imap_last_uid: int = 0
    last_sync_at: datetime | None
    created_at: datetime


class ImapAccountIn(BaseModel):
    address: EmailStr
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=993, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=512)
    use_ssl: bool = True
    folder: str = Field(default="INBOX", min_length=1, max_length=64)


class MailSyncResult(BaseModel):
    account_id: str
    kind: str
    fetched: int = 0
    accepted: int = 0
    duplicates: int = 0
    skipped: int = 0
    inbox_items: int = 0
    last_uid: int = 0
    last_sync_at: datetime | None = None


class MailRuleIn(BaseModel):
    kind: Literal["domain", "keyword", "mime"]
    value: str = Field(min_length=1, max_length=255)
    action: Literal["allow", "deny"] = "deny"
    enabled: bool = True


class MailRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    value: str
    action: str
    enabled: bool
    created_at: datetime


class InboxItemOut(BaseModel):
    id: str
    filename: str
    mime: str
    size: int
    status: str
    subject: str
    sender: str
    received_at: datetime
    created_at: datetime
    download_url: str


class ClaimIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)


class CompleteIn(BaseModel):
    status: Literal["done", "skipped"]
    device_id: str | None = Field(default=None, max_length=64)
    document_id: str | None = Field(default=None, max_length=36)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    status: str
    source: str
    source_ref: str | None
    document_date: datetime | None
    confidence: float | None
    created_at: datetime
    updated_at: datetime
    version: int
