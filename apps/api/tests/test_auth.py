from __future__ import annotations

from tests.conftest import auth_headers, register_user


async def test_register_login_and_me(client):
    data = await register_user(client)
    assert data["user"]["email"] == "user@example.com"
    assert data["token_type"] == "bearer"

    me = await client.get("/v1/auth/me", headers=auth_headers(data["access_token"]))
    assert me.status_code == 200
    assert me.json()["id"] == data["user"]["id"]

    login = await client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["id"] == data["user"]["id"]


async def test_duplicate_email_rejected(client):
    await register_user(client)
    response = await client.post(
        "/v1/auth/register",
        json={"email": "USER@example.com", "password": "password123"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


async def test_wrong_password_rejected(client):
    await register_user(client)
    response = await client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_refresh_rotation(client):
    data = await register_user(client)
    old_refresh = data["refresh_token"]

    refreshed = await client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 200
    new_refresh = refreshed.json()["refresh_token"]
    assert new_refresh != old_refresh

    reused = await client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401

    still_valid = await client.post("/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert still_valid.status_code == 200


async def test_me_requires_token(client):
    response = await client.get("/v1/auth/me")
    assert response.status_code == 401
