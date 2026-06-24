from fastapi import HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
import jwt as pyjwt
from config import settings
from typing import Optional


def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from backend bearer token."""
    if not authorization:
        raise HTTPException(401, "Missing auth token")
    try:
        token = authorization.replace("Bearer ", "")
        payload = pyjwt.decode(token, settings.BACKEND_JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub") or payload.get("email")
        if not user_id:
            raise ValueError("No subject in token")
        return user_id
    except Exception:
        raise HTTPException(401, "Invalid auth token")


async def assert_run_access(run, user_id: str, db: AsyncSession) -> None:
    """Raise HTTP 404 if user is neither the run owner nor a workspace member."""
    if run.user_id == user_id:
        return
    if run.workspace_id:
        from models import WorkspaceMember  # local import to avoid circular deps
        member = await db.get(WorkspaceMember, (run.workspace_id, user_id))
        if member:
            return
    raise HTTPException(404, "Run not found")
