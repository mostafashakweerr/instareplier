import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from instagram import get_client
from models import Campaign, Config

router = APIRouter(prefix="/api")
logger = logging.getLogger("api")


# ── Pydantic schemas ───────────────────────────────────────────────

class ConfigIn(BaseModel):
    access_token: str
    page_id: str
    instagram_account_id: str


class CampaignIn(BaseModel):
    post_id: str
    keywords: str
    comment_reply: str
    dm_message: str
    active: bool = True


class CampaignUpdate(BaseModel):
    post_id: Optional[str] = None
    keywords: Optional[str] = None
    comment_reply: Optional[str] = None
    dm_message: Optional[str] = None
    active: Optional[bool] = None


# ── Config ─────────────────────────────────────────────────────────

@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    cfg = db.query(Config).first()
    if not cfg:
        return {}
    return {
        "page_id": cfg.page_id,
        "instagram_account_id": cfg.instagram_account_id,
        "has_token": bool(cfg.access_token),
        "updated_at": cfg.updated_at,
    }


@router.post("/config")
def save_config(body: ConfigIn, db: Session = Depends(get_db)):
    cfg = db.query(Config).first()
    if not cfg:
        cfg = Config()
        db.add(cfg)
    cfg.access_token = body.access_token
    cfg.page_id = body.page_id
    cfg.instagram_account_id = body.instagram_account_id
    db.commit()
    return {"status": "saved"}


# ── Campaigns ──────────────────────────────────────────────────────

@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    return db.query(Campaign).order_by(Campaign.id.desc()).all()


@router.post("/campaigns")
async def create_campaign(body: CampaignIn, db: Session = Depends(get_db)):
    cfg = db.query(Config).first()
    thumbnail = caption = ""
    if cfg and cfg.access_token:
        client = get_client(cfg.access_token)
        try:
            details = await client.get_post_details(body.post_id)
            if details:
                thumbnail = details["thumbnail"]
                caption = details["caption"]
        finally:
            await client.close()

    campaign = Campaign(
        post_id=body.post_id,
        keywords=body.keywords,
        comment_reply=body.comment_reply,
        dm_message=body.dm_message,
        active=body.active,
        post_thumbnail=thumbnail,
        post_caption=caption,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, body: CampaignUpdate, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"status": "deleted"}


@router.patch("/campaigns/{campaign_id}/toggle")
def toggle_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.active = not campaign.active
    db.commit()
    return {"active": campaign.active}


# ── Post preview ───────────────────────────────────────────────────

@router.get("/post-preview/{post_id}")
async def post_preview(post_id: str, db: Session = Depends(get_db)):
    cfg = db.query(Config).first()
    if not cfg or not cfg.access_token:
        raise HTTPException(status_code=400, detail="No access token configured")
    client = get_client(cfg.access_token)
    try:
        details = await client.get_post_details(post_id)
    finally:
        await client.close()
    if not details:
        raise HTTPException(status_code=404, detail="Post not found or API error")
    return details
