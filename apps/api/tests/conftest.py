from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models  # noqa: F401
from app.db import Base, get_session
from app.main import app
from app.services.storage import LocalStorage, get_storage_dep


@pytest_asyncio.fixture
async def engine(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    test_engine = create_async_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path / "storage")


@pytest_asyncio.fixture
async def client(session_factory, storage):
    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_storage_dep] = lambda: storage
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def register_user(
    client: AsyncClient,
    email: str = "user@example.com",
    password: str = "password123",
) -> dict:
    response = await client.post(
        "/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_email(
    *,
    recipient: str,
    subject: str = "Результаты анализов",
    sender: str = "Лаборатория <lab@example.com>",
    body: str = "Результаты исследования во вложении.",
    attachment: bytes = b"%PDF-1.4\nsynthetic test pdf\n%%EOF\n",
    filename: str = "results.pdf",
    maintype: str = "application",
    subtype: str = "pdf",
    message_id: str = "<message-1@example.com>",
) -> bytes:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message["Message-ID"] = message_id
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    message.set_content(body)
    message.add_attachment(
        attachment,
        maintype=maintype,
        subtype=subtype,
        filename=filename,
    )
    return message.as_bytes()
