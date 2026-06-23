import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from database import get_db
from instagram import get_client
from models import Campaign, Config, ProcessedComment

router = APIRouter()
logger = logging.getLogger("webhook")

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "changeme")
APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "")


def _verify_signature(body: bytes, sig_header: str) -> bool:
    if not APP_SECRET or not sig_header:
        logger.warning("Signature check skipped — APP_SECRET not set")
        return True  # dev mode
    expected = "sha256=" + hmac.new(
        APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


# ── Webhook challenge verification ────────────────────────────────
@router.get("/webhook/instagram")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified ✓")
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


# ── Incoming events ────────────────────────────────────────────────
@router.post("/webhook/instagram")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    body_bytes = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_signature(body_bytes, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Bad JSON")

    logger.info("Webhook payload: %s", payload)

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            val = change.get("value", {})
            await _handle_comment(val, db)

    return {"status": "ok"}


async def _handle_comment(val: dict, db: Session):
    comment_id = val.get("id")
    post_id = val.get("media", {}).get("id") or val.get("post_id")
    commenter_id = val.get("from", {}).get("id")
    text = (val.get("text") or "").strip().lower()

    if not comment_id or not post_id or not commenter_id:
        logger.warning("Incomplete comment event: %s", val)
        return

    # Deduplication check
    existing = db.query(ProcessedComment).filter_by(comment_id=comment_id).first()
    if existing:
        logger.info("Comment %s already processed, skipping", comment_id)
        return

    # Find matching active campaign
    campaigns = db.query(Campaign).filter_by(active=True).all()
    matched: Campaign | None = None
    for campaign in campaigns:
        if campaign.post_id != post_id:
            continue
        keywords = [k.strip().lower() for k in campaign.keywords.split(",") if k.strip()]
        if any(kw in text for kw in keywords):
            matched = campaign
            break

    if not matched:
        logger.debug("No campaign matched for post %s / comment '%s'", post_id, text)
        return

    # Mark as processed immediately to prevent race conditions
    db.add(ProcessedComment(comment_id=comment_id, campaign_id=matched.id))
    db.commit()

    config = db.query(Config).first()
    if not config or not config.access_token:
        logger.error("No access token configured")
        return

    client = get_client(config.access_token)
    try:
        logger.info("Replying to comment %s", comment_id)
        await client.reply_to_comment(comment_id, matched.comment_reply)

        logger.info("Sending DM to user %s", commenter_id)
        await client.send_dm(commenter_id, matched.dm_message)
    finally:
        await client.close()
