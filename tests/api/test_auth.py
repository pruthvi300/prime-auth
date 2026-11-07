from tests.conftest import API, login, register


async def test_register_returns_public_fields_only(client):
    response = await client.post(
        f"{API}/auth/register",
        json={"email": "Test@Example.com", "password": "strongpassword123", "full_name": "Test User"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"  # normalised
    assert data["is_active"] is True
    assert "hashed_password" not in data


async def test_register_duplicate_email_is_conflict(client):
    await register(client)
    response = await register(client, email="USER@example.com")
    assert response.status_code == 409


async def test_register_rejects_short_password(client):
    response = await register(client, password="short")
    assert response.status_code == 422


async def test_register_ignores_client_supplied_flags(client):
    response = await client.post(
        f"{API}/auth/register",
        json={"email": "x@example.com", "password": "strongpassword123", "is_active": False, "is_superuser": True},
    )
    assert response.status_code == 201
    assert response.json()["is_active"] is True


async def test_login_success(client):
    await register(client)
    response = await login(client)
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"] and data["refresh_token"]


async def test_login_wrong_password_and_unknown_email_look_the_same(client):
    await register(client)
    wrong_password = await login(client, password="wrongpassword1")
    unknown_email = await login(client, email="nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


async def test_me_requires_valid_access_token(client):
    await register(client)
    tokens = (await login(client)).json()

    ok = await client.get(f"{API}/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert ok.status_code == 200
    assert ok.json()["email"] == "user@example.com"

    assert (await client.get(f"{API}/users/me")).status_code == 401
    # A refresh token must not work as an access token.
    wrong_type = await client.get(f"{API}/users/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert wrong_type.status_code == 401


async def test_refresh_rotates_tokens(client):
    await register(client)
    first = (await login(client)).json()

    response = await client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert response.status_code == 200
    second = response.json()
    assert second["refresh_token"] != first["refresh_token"]

    me = await client.get(f"{API}/users/me", headers={"Authorization": f"Bearer {second['access_token']}"})
    assert me.status_code == 200


async def test_refresh_token_reuse_revokes_the_whole_family(client):
    await register(client)
    first = (await login(client)).json()
    second = (await client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})).json()

    # Replaying the already-used token is detected...
    replay = await client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401
    # ...and the legitimate newer token is revoked too.
    newer = await client.post(f"{API}/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert newer.status_code == 401


async def test_other_sessions_survive_reuse_in_one_session(client):
    await register(client)
    session_a = (await login(client)).json()
    session_b = (await login(client)).json()
    await client.post(f"{API}/auth/refresh", json={"refresh_token": session_a["refresh_token"]})
    await client.post(f"{API}/auth/refresh", json={"refresh_token": session_a["refresh_token"]})  # reuse

    response = await client.post(f"{API}/auth/refresh", json={"refresh_token": session_b["refresh_token"]})
    assert response.status_code == 200


async def test_access_token_cannot_be_used_to_refresh(client):
    await register(client)
    tokens = (await login(client)).json()
    response = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert response.status_code == 401


async def test_logout_revokes_refresh_token(client):
    await register(client)
    tokens = (await login(client)).json()
    assert (await client.post(f"{API}/auth/logout", json={"refresh_token": tokens["refresh_token"]})).status_code == 204
    response = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401


async def test_login_is_rate_limited(client):
    from app.core.rate_limit import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        statuses = [(await login(client, email="nobody@example.com")).status_code for _ in range(6)]
    finally:
        limiter.enabled = False
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429
