"""
Instagram Graph API client.
All calls use the long-lived User Access Token stored in the DB Config row.
"""
import asyncio
import logging
from typing import Optional

import httpx

BASE = "https://graph.facebook.com/v19.0"
logger = logging.getLogger("instagram")


class InstagramClient:
    def __init__(self, access_token: str):
        self.token = access_token
        self._client = httpx.AsyncClient(timeout=15)

    async def _get(self, path: str, **params) -> dict:
        params["access_token"] = self.token
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, **data) -> dict:
        data["access_token"] = self.token
        return await self._request("POST", path, data=data)

    async def _request(self, method: str, path: str, *, params=None, data=None, _retry=3) -> dict:
        url = f"{BASE}{path}"
        for attempt in range(_retry):
            try:
                if method == "GET":
                    r = await self._client.get(url, params=params)
                else:
                    r = await self._client.post(url, data=data)
                body = r.json()
                logger.info("IG API %s %s → %s", method, path, r.status_code)
                if "error" in body:
                    code = body["error"].get("code")
                    # Rate-limit codes: 4, 17, 32, 613
                    if code in (4, 17, 32, 613) and attempt < _retry - 1:
                        wait = 2 ** (attempt + 1)
                        logger.warning("Rate limit hit, retrying in %ss", wait)
                        await asyncio.sleep(wait)
                        continue
                    logger.error("IG API error: %s", body["error"])
                return body
            except httpx.RequestError as exc:
                logger.error("HTTP error on attempt %d: %s", attempt + 1, exc)
                if attempt < _retry - 1:
                    await asyncio.sleep(2 ** attempt)
        return {"error": {"message": "Max retries exceeded"}}

    # ── Public methods ──────────────────────────────────────────

    async def reply_to_comment(self, comment_id: str, message: str) -> dict:
        """Post a public reply to a comment."""
        result = await self._post(f"/{comment_id}/replies", message=message)
        logger.info("reply_to_comment %s → %s", comment_id, result)
        return result

    async def send_dm(self, instagram_user_id: str, message: str) -> dict:
        """
        Send a private DM via the Instagram Messaging API.
        Requires instagram_manage_messages permission.
        The recipient must have previously messaged the business OR the
        business must have the approved messaging use case.
        """
        payload = {
            "recipient": {"id": instagram_user_id},
            "message": {"text": message},
        }
        # The send-message endpoint requires the Page access token scoped to the IG account
        result = await self._post("/me/messages", **{
            "recipient": f'{{"id":"{instagram_user_id}"}}',
            "message": f'{{"text":{message!r}}}',
        })
        # Alternative cleaner form (Graph API accepts flat JSON too via form-data):
        r = await self._client.post(
            f"{BASE}/me/messages",
            params={"access_token": self.token},
            json={"recipient": {"id": instagram_user_id}, "message": {"text": message}},
        )
        result = r.json()
        logger.info("send_dm %s → %s", instagram_user_id, result)
        return result

    async def get_post_details(self, post_id: str) -> Optional[dict]:
        """Fetch thumbnail URL + caption for a given media ID."""
        data = await self._get(
            f"/{post_id}",
            fields="id,caption,thumbnail_url,media_url,media_type,permalink",
        )
        if "error" in data:
            return None
        return {
            "id": data.get("id"),
            "caption": (data.get("caption") or "")[:200],
            "thumbnail": data.get("thumbnail_url") or data.get("media_url") or "",
            "permalink": data.get("permalink", ""),
            "media_type": data.get("media_type", ""),
        }

    async def close(self):
        await self._client.aclose()


def get_client(access_token: str) -> InstagramClient:
    return InstagramClient(access_token)
