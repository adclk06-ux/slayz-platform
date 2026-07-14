"""
SQLAlchemy ORM models: Users (RBAC), Articles (news + AI analysis), AuditLog.
Sensitive columns use an EncryptedString TypeDecorator for encryption at rest.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import relationship

from app.database import Base
from app.security import decrypt_value, encrypt_value


class EncryptedString(TypeDecorator):
    """Transparent Fernet-encrypted string column (encryption at rest)."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return decrypt_value(value)


def gen_uuid() -> str:
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class UserStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    AVAILABLE = "available"
    BUSY = "busy"


class RoomType(str, enum.Enum):
    DIRECT = "direct"
    GROUP = "group"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"


class ArticleStatus(str, enum.Enum):
    PENDING_ANALYSIS = "pending_analysis"
    ANALYZED = "analyzed"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class NewsCategory(str, enum.Enum):
    CRYPTO = "crypto"
    STOCKS = "stocks"
    COMMODITIES = "commodities"
    GENERAL = "general"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    full_name = Column(String(255), nullable=False)
    email = Column(String(320), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.VIEWER)
    is_active = Column(Boolean, default=True, nullable=False)
    # Workspace presence fields for the WhatsApp-style desk chat.
    avatar_url = Column(String(1024), nullable=True)
    status = Column(SAEnum(UserStatus), nullable=False, default=UserStatus.AVAILABLE)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    room_memberships = relationship("RoomMember", back_populates="user")


class Article(Base):
    __tablename__ = "articles"

    id = Column(String, primary_key=True, default=gen_uuid)

    source_name = Column(String(255), nullable=False)
    source_url = Column(String(2048), nullable=False, unique=True)
    category = Column(SAEnum(NewsCategory), nullable=False, default=NewsCategory.GENERAL)

    raw_title = Column(String(1024), nullable=False)
    raw_content = Column(EncryptedString, nullable=False)

    ai_title = Column(String(1024), nullable=True)
    ai_summary = Column(EncryptedString, nullable=True)
    sentiment = Column(String(32), nullable=True)  # bullish / bearish / neutral

    status = Column(SAEnum(ArticleStatus), nullable=False, default=ArticleStatus.PENDING_ANALYSIS)
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    email_sent = Column(Boolean, default=False, nullable=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    analyzed_at = Column(DateTime, nullable=True)

    # --- Institutional-grade enrichment fields ---
    # Tickers discovered in the article text (e.g. ["THYAO", "AAPL", "NVDA"]).
    extracted_tickers = Column(Text, nullable=True)
    # Largest associated market cap in USD, when available.
    market_cap_usd = Column(String(64), nullable=True)
    # True when the headline company is a mega-cap (> $100B USD).
    is_mega_cap = Column(Boolean, default=False, nullable=False)
    # Macro region this article belongs to: US, TR, JP, EZ, or empty.
    macro_region = Column(String(8), nullable=True)
    # High-impact macro indicator: interest, employment, gdp, or empty.
    macro_indicator = Column(String(32), nullable=True)
    # Deduplication group id. Articles in the same group are near-duplicates.
    duplicate_group_id = Column(String(64), nullable=True, index=True)
    # Whether this article is the canonical (primary) card for its duplicate group.
    is_primary_duplicate = Column(Boolean, default=True, nullable=False)
    # JSON list of secondary source names merged into the primary card.
    duplicate_source_names = Column(Text, nullable=True)

    reviewer = relationship("User", foreign_keys=[reviewed_by])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(String, nullable=True)
    action = Column(String(255), nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BriefingSnapshot(Base):
    """Scheduled briefing engine output.

    Stores the list of unreviewed articles ingested since the previous snapshot
    and the hyper-condensed macro summary generated by the LLM.
    """

    __tablename__ = "briefing_snapshots"

    id = Column(String, primary_key=True, default=gen_uuid)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Triggers are scheduled at 08:00 and 16:00 (e.g. "08:00" / "16:00").
    slot = Column(String(8), nullable=False)
    article_ids = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    word_count = Column(Integer, nullable=False)


class InboxMessage(Base):
    """Internal shared inbox for team collaboration and institutional alerts.

    Used for operational updates, research notes, and structured alerts sent
    by team members or senior analysts.
    """

    __tablename__ = "inbox_messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    sender_name = Column(String(255), nullable=False)
    sender_avatar = Column(String(1024), nullable=True)
    title = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    associated_ticker = Column(String(32), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Room(Base):
    """Chat room: either a direct (1-1) conversation or a group channel."""

    __tablename__ = "rooms"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=True)
    type = Column(SAEnum(RoomType), nullable=False, default=RoomType.GROUP)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    # For DIRECT rooms: sorted pair of participant ids prevents duplicate 1-1 rooms.
    direct_user_a_id = Column(String, ForeignKey("users.id"), nullable=True)
    direct_user_b_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        # Ensure a given user pair has exactly one direct room.
        Index(
            "ix_rooms_direct_participants",
            "direct_user_a_id",
            "direct_user_b_id",
            unique=True,
            postgresql_where=(direct_user_a_id.isnot(None)),
            sqlite_where=(direct_user_a_id.isnot(None)),
        ),
    )

    members = relationship("RoomMember", back_populates="room", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="room", cascade="all, delete-orphan")


class RoomMember(Base):
    """Membership of a user in a chat room with read tracking."""

    __tablename__ = "room_members"

    room_id = Column(String, ForeignKey("rooms.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_read_message_id = Column(String, ForeignKey("messages.id"), nullable=True)
    last_read_at = Column(DateTime, nullable=True)

    room = relationship("Room", back_populates="members")
    user = relationship("User", back_populates="room_memberships")


class Message(Base):
    """Real-time chat message persisted for history and offline replay."""

    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False, index=True)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=True)
    message_type = Column(SAEnum(MessageType), nullable=False, default=MessageType.TEXT)
    reply_to_id = Column(String, ForeignKey("messages.id"), nullable=True)
    edited_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    room = relationship("Room", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")


class MessageAttachment(Base):
    """File metadata linked to a chat message."""

    __tablename__ = "message_attachments"

    id = Column(String, primary_key=True, default=gen_uuid)
    message_id = Column(String, ForeignKey("messages.id"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(2048), nullable=False)
    mime_type = Column(String(128), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    message = relationship("Message", back_populates="attachments")


class ChatMessage(Base):
    """DEPRECATED: legacy direct-message storage.

    Kept temporarily so the existing /api/chat router can import it while the
    room-based chat system is being migrated. Will be removed once the new
    Room/Message endpoints fully replace it.
    """

    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    sender_name = Column(String(255), nullable=False)
    recipient_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    article_id = Column(String(64), nullable=True)
    article_title = Column(String(1024), nullable=True)
    ticker = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketTicker(Base):
    __tablename__ = "market_tickers"

    id = Column(String, primary_key=True, default=gen_uuid)
    symbol = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(32), nullable=False)  # index, commodity, equity, crypto
    price = Column(String(64), nullable=True)
    change = Column(String(64), nullable=True)
    change_percent = Column(String(64), nullable=True)
    currency = Column(String(8), nullable=True)
    source = Column(String(255), nullable=True)
    is_simulated = Column(Boolean, default=False, nullable=False)
    history_json = Column(Text, nullable=True)  # JSON array of [ts, price]
    last_updated = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
