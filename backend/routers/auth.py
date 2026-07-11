from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User
from schemas import (
    RegisterRequest, RegisterResponse, LoginRequest, UserResponse,
    VerifyEmailRequest, VerifyEmailResponse, ResendVerificationRequest,
    SimpleStatusResponse,
)
from auth import (
    hash_password, verify_password,
    create_email_verification_token, verify_email_verification_token,
)
from config import settings
from utils.email import send_verification_email

# Unauthenticated router: these endpoints ARE the login path, so they must not
# depend on get_current_user. NextAuth's CredentialsProvider calls /auth/login.
router = APIRouter()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _send_verification(email: str) -> str:
    """Mint a verification token, build the link, dispatch the email, return the URL."""
    token = create_email_verification_token(email)
    url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    send_verification_email(email, url)
    return url


def _dev_url(url: str) -> str | None:
    """Expose the link in responses only in development, so tests/manual runs
    don't need a real inbox. Never leaked in production."""
    return url if settings.ENVIRONMENT != "production" else None


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email = _normalize_email(body.email)
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(body.password), name=body.name)
    db.add(user)
    await db.commit()

    url = _send_verification(email)
    return RegisterResponse(
        email=user.email, name=user.name,
        verification_required=True, dev_verification_url=_dev_url(url),
    )


@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    email = verify_email_verification_token(body.token)
    if not email:
        raise HTTPException(400, "This verification link is invalid or has expired.")
    result = await db.execute(select(User).where(User.email == _normalize_email(email)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(400, "This verification link is invalid or has expired.")
    if user.email_verified_at is None:  # idempotent: re-verifying is a no-op
        user.email_verified_at = datetime.now(timezone.utc)
        await db.commit()
    return VerifyEmailResponse(email=user.email, verified=True)


@router.post("/resend-verification", response_model=SimpleStatusResponse)
async def resend_verification(body: ResendVerificationRequest, db: AsyncSession = Depends(get_db)):
    email = _normalize_email(body.email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    # Always return ok (no enumeration); only actually send for an existing,
    # still-unverified account.
    dev_url = None
    if user and user.email_verified_at is None:
        dev_url = _dev_url(_send_verification(email))
    return SimpleStatusResponse(status="ok", dev_verification_url=dev_url)


@router.post("/login", response_model=UserResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    email = _normalize_email(body.email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    # Same 401 whether the email is unknown or the password is wrong, so the
    # response doesn't reveal which emails have accounts.
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password.")
    if user.email_verified_at is None:
        raise HTTPException(403, "Please verify your email before signing in.")
    return UserResponse(email=user.email, name=user.name)
