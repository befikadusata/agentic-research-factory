"""
Publisher Agent — posts formatted content to LinkedIn and/or Buffer.

Env vars required:
  LINKEDIN_ACCESS_TOKEN=...
  BUFFER_ACCESS_TOKEN=...
  BUFFER_PROFILE_IDS=id1,id2   (comma-separated Buffer profile IDs)
"""
import httpx
from config import settings


async def publish_to_linkedin(content: str, scheduled_at: str | None = None) -> dict:
    """
    POST to LinkedIn UGC Posts API.
    scheduled_at: ISO-8601 string, or None to post immediately.
    Requires LINKEDIN_ACCESS_TOKEN and the user's LinkedIn URN.
    """
    token = getattr(settings, "LINKEDIN_ACCESS_TOKEN", None)
    if not token:
        return {"error": "LINKEDIN_ACCESS_TOKEN not configured"}

    # Fetch the authenticated member's URN
    async with httpx.AsyncClient() as client:
        me = await client.get(
            "https://api.linkedin.com/v2/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        me.raise_for_status()
        author_urn = f"urn:li:person:{me.json()['id']}"

        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        resp = await client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Restli-Protocol-Version": "2.0.0",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def publish_to_buffer(content: str, scheduled_at: str | None = None) -> dict:
    """
    POST to Buffer API.
    scheduled_at: Unix timestamp string, or None to add to queue.
    Requires BUFFER_ACCESS_TOKEN and BUFFER_PROFILE_IDS.
    """
    token = getattr(settings, "BUFFER_ACCESS_TOKEN", None)
    profile_ids_raw = getattr(settings, "BUFFER_PROFILE_IDS", "")
    if not token or not profile_ids_raw:
        return {"error": "BUFFER_ACCESS_TOKEN or BUFFER_PROFILE_IDS not configured"}

    profile_ids = [p.strip() for p in profile_ids_raw.split(",") if p.strip()]
    payload: dict = {"text": content, "profile_ids[]": profile_ids}
    if scheduled_at:
        payload["scheduled_at"] = scheduled_at

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.bufferapp.com/1/updates/create.json",
            data=payload,
            params={"access_token": token},
        )
        resp.raise_for_status()
        return resp.json()
