"""
Pydantic schemas for request/response validation.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import ArticleStatus, MessageType, NewsCategory, RoomType, UserRole, UserStatus


# --- Auth ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    full_name: str


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.VIEWER


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class SetupStatusOut(BaseModel):
    needs_setup: bool
    allowed_email_domain: str


class UserOut(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    avatar_url: Optional[str] = None
    status: UserStatus
    last_seen_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Chat ---
class RoomMemberUserOut(BaseModel):
    id: str
    full_name: str
    email: str
    avatar_url: Optional[str] = None
    status: UserStatus
    is_online: bool = False


class LastMessageOut(BaseModel):
    id: str
    content: Optional[str]
    created_at: datetime
    sender: RoomMemberUserOut


class RoomOut(BaseModel):
    id: str
    name: Optional[str]
    type: RoomType
    avatar_url: Optional[str] = None
    members: List[RoomMemberUserOut]
    last_message: Optional[LastMessageOut] = None
    unread_count: int = 0
    updated_at: datetime


class MessageAttachmentOut(BaseModel):
    id: str
    file_name: str
    file_url: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class MessageOut(BaseModel):
    id: str
    room_id: str
    content: Optional[str]
    message_type: MessageType
    created_at: datetime
    edited_at: Optional[datetime] = None
    sender: RoomMemberUserOut
    attachments: List[MessageAttachmentOut] = []


class RoomCreate(BaseModel):
    type: RoomType
    name: Optional[str] = Field(default=None, max_length=255)
    member_ids: List[str] = Field(min_length=1, max_length=100)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class MessageReadReceipt(BaseModel):
    room_id: str
    message_id: str
    read_at: datetime


class MessageListOut(BaseModel):
    messages: List[MessageOut]
    next_cursor: Optional[str] = None
    has_more: bool


# --- Articles ---
class ArticleOut(BaseModel):
    id: str
    source_name: str
    source_url: str
    category: NewsCategory
    raw_title: str
    raw_content: str
    ai_title: Optional[str] = None
    ai_summary: Optional[str] = None
    sentiment: Optional[str] = None
    status: ArticleStatus
    email_sent: bool
    scraped_at: datetime
    analyzed_at: Optional[datetime] = None

    # Institutional-grade enrichment fields
    extracted_tickers: Optional[List[str]] = None
    market_cap_usd: Optional[str] = None
    is_mega_cap: bool = False
    macro_region: Optional[str] = None
    macro_indicator: Optional[str] = None
    duplicate_group_id: Optional[str] = None
    is_primary_duplicate: bool = True
    duplicate_source_names: Optional[List[str]] = None

    @field_validator("extracted_tickers", "duplicate_source_names", mode="before")
    @classmethod
    def _parse_json_lists(cls, value):
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        return []

    class Config:
        from_attributes = True


class ArticleFilterParams(BaseModel):
    category: Optional[NewsCategory] = None
    status_filter: Optional[ArticleStatus] = None
    mega_cap_only: Optional[bool] = None
    macro_region: Optional[str] = None
    macro_indicator: Optional[str] = None


class ArticleReviewAction(BaseModel):
    approve: bool


class ScrapeTriggerResponse(BaseModel):
    scraped: int
    analyzed: int
    emailed: int


class ShareArticleRequest(BaseModel):
    email: EmailStr
    note: Optional[str] = Field(default=None, max_length=1000)


class BriefingSnapshotOut(BaseModel):
    id: str
    created_at: datetime
    slot: str
    article_ids: List[str]
    summary: str
    word_count: int

    @field_validator("article_ids", mode="before")
    @classmethod
    def _parse_article_ids(cls, value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        return []

    class Config:
        from_attributes = True


class InboxMessageOut(BaseModel):
    id: str
    sender_id: str
    recipient_id: Optional[str] = None
    sender_name: str
    sender_avatar: Optional[str] = None
    title: str
    content: str
    associated_ticker: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class InboxMessageCreate(BaseModel):
    recipient_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=512)
    content: str = Field(min_length=1, max_length=8000)
    associated_ticker: Optional[str] = Field(default=None, max_length=32)


class ChatMessageOut(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    recipient_id: Optional[str] = None
    content: str
    article_id: Optional[str] = None
    article_title: Optional[str] = None
    ticker: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatUserOut(BaseModel):
    """Workspace member entry for the WhatsApp-style desk chat roster."""

    id: str
    full_name: str
    role: str
    avatar_url: Optional[str] = None
    status: str = "available"
    is_online: bool = False
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None


class ChatSendPayload(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    article_id: Optional[str] = None
    article_title: Optional[str] = None
    ticker: Optional[str] = Field(default=None, max_length=32)


# --- AI Assistant ---
class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class AssistantChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(min_length=1, max_length=20)


class AssistantChatResponse(BaseModel):
    reply: str
    action: Optional[Dict] = None


class TickerHistoryPoint(BaseModel):
    ts: float
    price: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None


class TickerOut(BaseModel):
    id: str
    symbol: str
    name: str
    category: str
    price: Optional[str] = None
    change: Optional[str] = None
    change_percent: Optional[str] = None
    currency: Optional[str] = None
    source: Optional[str] = None
    is_simulated: bool
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True
