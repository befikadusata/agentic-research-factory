import pytest


REG = "/auth/register"
LOGIN = "/auth/login"
VERIFY = "/auth/verify-email"
RESEND = "/auth/resend-verification"


def _token_from(url: str) -> str:
    return url.split("token=")[1]


async def _register(client, email, password="hunter2pass", name=None):
    return await client.post(REG, json={"email": email, "password": password, "name": name})


async def _register_and_verify(client, email, password="hunter2pass", name=None):
    r = await _register(client, email, password, name)
    token = _token_from(r.json()["dev_verification_url"])
    await client.post(VERIFY, json={"token": token})
    return r


# --- registration ---------------------------------------------------------

@pytest.mark.asyncio
async def test_register_creates_unverified_account(client):
    r = await _register(client, "alice@example.com", name="Alice")
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["verification_required"] is True
    assert body["dev_verification_url"]  # present in dev


@pytest.mark.asyncio
async def test_duplicate_registration_is_conflict(client):
    await _register(client, "dup@example.com")
    r = await _register(client, "DUP@example.com")
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_short_password_rejected(client):
    r = await client.post(REG, json={"email": "eve@example.com", "password": "short"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_password_hash_is_not_plaintext(client, db_session):
    from sqlalchemy import select
    from models import User

    await _register(client, "frank@example.com")
    user = (await db_session.execute(select(User).where(User.email == "frank@example.com"))).scalar_one()
    assert user.password_hash != "hunter2pass"
    assert user.password_hash.startswith("$2")  # bcrypt marker


# --- login gating on verification ----------------------------------------

@pytest.mark.asyncio
async def test_login_before_verification_is_forbidden(client):
    await _register(client, "carol@example.com")
    r = await client.post(LOGIN, json={"email": "carol@example.com", "password": "hunter2pass"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_login_after_verification_succeeds(client):
    await _register_and_verify(client, "carol@example.com", name="Carol")
    r = await client.post(LOGIN, json={"email": "carol@example.com", "password": "hunter2pass"})
    assert r.status_code == 200
    assert r.json()["email"] == "carol@example.com"


@pytest.mark.asyncio
async def test_email_normalized_lowercase(client):
    await _register_and_verify(client, "Bob@Example.com")
    r = await client.post(LOGIN, json={"email": "bob@EXAMPLE.com", "password": "hunter2pass"})
    assert r.status_code == 200
    assert r.json()["email"] == "bob@example.com"


@pytest.mark.asyncio
async def test_wrong_password_is_401_even_when_verified(client):
    await _register_and_verify(client, "dave@example.com")
    r = await client.post(LOGIN, json={"email": "dave@example.com", "password": "nope"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_unknown_email_and_wrong_password_indistinguishable(client):
    await _register_and_verify(client, "erin@example.com")
    unknown = await client.post(LOGIN, json={"email": "ghost@example.com", "password": "hunter2pass"})
    wrong = await client.post(LOGIN, json={"email": "erin@example.com", "password": "bad"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()  # no enumeration


# --- verify-email endpoint -----------------------------------------------

@pytest.mark.asyncio
async def test_verify_with_invalid_token_is_400(client):
    r = await client.post(VERIFY, json={"token": "not-a-real-token"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_verify_is_idempotent(client):
    r = await _register(client, "gina@example.com")
    token = _token_from(r.json()["dev_verification_url"])
    first = await client.post(VERIFY, json={"token": token})
    second = await client.post(VERIFY, json={"token": token})
    assert first.status_code == second.status_code == 200
    assert second.json()["verified"] is True


# --- resend ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_resend_for_unverified_sends_link(client):
    await _register(client, "harry@example.com")
    r = await client.post(RESEND, json={"email": "harry@example.com"})
    assert r.status_code == 200
    assert r.json()["dev_verification_url"]


@pytest.mark.asyncio
async def test_resend_for_verified_sends_nothing(client):
    await _register_and_verify(client, "iris@example.com")
    r = await client.post(RESEND, json={"email": "iris@example.com"})
    assert r.status_code == 200
    assert r.json()["dev_verification_url"] is None


@pytest.mark.asyncio
async def test_resend_for_unknown_email_does_not_enumerate(client):
    r = await client.post(RESEND, json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["dev_verification_url"] is None
