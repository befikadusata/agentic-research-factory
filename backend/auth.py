from fastapi import HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
import jwt as pyjwt
import bcrypt
import time
from config import settings
from typing import Optional

_EMAIL_VERIFY_PURPOSE = "email_verify"


def create_email_verification_token(email: str, expires_hours: int = 24) -> str:
    """Signed, stateless token proving the bearer controls `email`.

    The `purpose` claim scopes it to email verification so it can't be replayed
    as a login/auth token even though it shares BACKEND_JWT_SECRET.
    """
    payload = {
        "sub": email,
        "purpose": _EMAIL_VERIFY_PURPOSE,
        "exp": int(time.time()) + expires_hours * 3600,
    }
    return pyjwt.encode(payload, settings.BACKEND_JWT_SECRET, algorithm="HS256")


def verify_email_verification_token(token: str) -> Optional[str]:
    """Return the email if the token is a valid, unexpired verify token, else None."""
    try:
        payload = pyjwt.decode(token, settings.BACKEND_JWT_SECRET, algorithms=["HS256"])
        if payload.get("purpose") != _EMAIL_VERIFY_PURPOSE:
            return None
        return payload.get("sub")
    except Exception:
        return None


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (per-hash random salt)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time verify of a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from backend bearer token."""
    if not authorization:
        raise HTTPException(401, "Missing auth token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Invalid auth token")
    try:
        payload = pyjwt.decode(token, settings.BACKEND_JWT_SECRET, algorithms=["HS256"])
        # Reject special-purpose tokens (e.g. email verification). Those share
        # the signing secret but travel through email/URLs/logs and must never
        # be usable as an API credential. Auth tokens carry no `purpose` claim.
        if payload.get("purpose"):
            raise ValueError("Not an auth token")
        user_id = payload.get("sub") or payload.get("email")
        if not user_id:
            raise ValueError("No subject in token")
        return user_id
    except Exception:
        raise HTTPException(401, "Invalid auth token")


_ROLE_RANK = {"viewer": 0, "operator": 1, "admin": 2}


def role_meets(role: Optional[str], min_role: str) -> bool:
    """True if a workspace role ranks at or above `min_role`.

    The single place workspace roles are ordered. An absent or unrecognised role
    ranks lowest rather than raising, so a row written by an older version — or
    by hand — degrades to the least privilege instead of an opaque 500.
    """
    return _ROLE_RANK.get(role or "", 0) >= _ROLE_RANK[min_role]


async def assert_run_access(run, user_id: str, db: AsyncSession, min_role: Optional[str] = None) -> None:
    """Raise HTTP 404 if user is neither the run owner nor a workspace member.

    If `min_role` is given, a workspace member whose role ranks below it is
    denied with 403 — e.g. a "viewer" must not be able to approve/resume a
    HITL-gated run. The run owner always passes regardless of role, since
    workspace role only governs access granted *via* the workspace.
    """
    if run.user_id == user_id:
        return
    if run.workspace_id:
        from models import WorkspaceMember  # local import to avoid circular deps
        member = await db.get(WorkspaceMember, (run.workspace_id, user_id))
        if member:
            if min_role is not None and not role_meets(member.role, min_role):
                raise HTTPException(403, f"Requires '{min_role}' role or higher in this workspace")
            return
    raise HTTPException(404, "Run not found")
