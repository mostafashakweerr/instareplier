from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(Text, nullable=True)
    page_id = Column(String(64), nullable=True)
    instagram_account_id = Column(String(64), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String(64), nullable=False)
    keywords = Column(Text, nullable=False)          # comma-separated
    comment_reply = Column(Text, nullable=False)
    dm_message = Column(Text, nullable=False)
    active = Column(Boolean, default=True)
    post_thumbnail = Column(Text, nullable=True)
    post_caption = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProcessedComment(Base):
    __tablename__ = "processed_comments"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String(64), unique=True, nullable=False, index=True)
    campaign_id = Column(Integer, nullable=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
