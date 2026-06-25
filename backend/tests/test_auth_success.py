import pytest
import time
import jwt as pyjwt
from httpx import AsyncClient, ASGITransport
from main import app
from config import settings


def _make_token(payload: dict, secret: str = None, algorithm: str = "HS256") -> str:
    secret = secret or settings.BACKEND_JWT_SECRET
    return pyjwt.encode(payload, secret, algorithm=algorithm)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_valid_token_with_sub_authenticates(client):
    token = _make_token({"sub": "user-from-sub"})
    r = await client.get("/runs", headers=_auth_header(token))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_token_with_email_no_sub_uses_email(client):
    token = _make_token({"email": "user@example.com"})
    r = await client.get("/runs", headers=_auth_header(token))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_invalid_signature_returns_401(client):
    token = _make_token({"sub": "user"}, secret="wrong-secret")
    r = await client.get("/runs", headers=_auth_header(token))
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_returns_401(client):
    token = _make_token({"sub": "user", "exp": int(time.time()) - 3600})
    r = await client.get("/runs", headers=_auth_header(token))
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_token_without_sub_or_email_returns_401(client):
    token = _make_token({"name": "Someone", "iat": int(time.time())})
    r = await client.get("/runs", headers=_auth_header(token))
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_malformed_bearer_token_returns_401(client):
    r = await client.get("/runs", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_missing_authorization_header_returns_401(client):
    r = await client.get("/runs")
    assert r.status_code == 401
