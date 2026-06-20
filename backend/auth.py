from fastapi import HTTPException, Header
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
