import pytest


@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post("/api/auth/register", json={
        "email": "new@example.com",
        "password": "password123",
        "full_name": "Test User",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert data["full_name"] == "Test User"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_weak_password(client):
    resp = await client.post("/api/auth/register", json={
        "email": "weak@example.com", "password": "123"
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/auth/register", json={
        "email": "login@example.com", "password": "password123"
    })
    resp = await client.post("/api/auth/login", data={
        "username": "login@example.com", "password": "password123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post("/api/auth/login", data={
        "username": "nobody@example.com", "password": "wrong"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me(client, auth_headers):
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert "email" in resp.json()


@pytest.mark.asyncio
async def test_me_no_token(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client):
    await client.post("/api/auth/register", json={
        "email": "refresh@example.com", "password": "password123"
    })
    login = await client.post("/api/auth/login", data={
        "username": "refresh@example.com", "password": "password123"
    })
    refresh_token = login.json()["refresh_token"]
    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_api_key_create_and_use(client, auth_headers):
    # Создаём ключ
    resp = await client.post("/api/auth/api-keys", json={
        "name": "Test Key",
        "expires_days": 30,
        "permissions": {"read": True, "write": True, "delete": False},
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "key" in data  # полный ключ только при создании
    raw_key = data["key"]

    # Используем ключ как аутентификацию
    resp2 = await client.get("/api/auth/me", headers={"X-API-Key": raw_key})
    assert resp2.status_code == 200
