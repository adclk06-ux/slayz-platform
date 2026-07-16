"""
Room-based chat REST endpoints.

Provides the authenticated user's room list, room membership checks, message
history pagination, and message creation. Real-time delivery is handled by
Socket.IO (see app/socketio_events.py).
"""
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Message, MessageType, Room, RoomMember, RoomType, User
from app.schemas import (
    MessageCreate,
    MessageListOut,
    MessageOut,
    RoomCreate,
    RoomMemberUserOut,
    RoomOut,
)
from app.security import get_current_user_payload
from app.socketio_server import is_user_online, join_user_to_room, sio

logger = logging.getLogger("slayz.rooms")
router = APIRouter(prefix="/api/rooms", tags=["rooms"])


def _member_user_out(user: User, *, is_online: bool = False) -> RoomMemberUserOut:
    return RoomMemberUserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        avatar_url=user.avatar_url,
        status=user.status,
        is_online=is_online or is_user_online(user.id),
    )


def _build_room_out(db: Session, room: Room, user_id: str) -> RoomOut:
    """Build a RoomOut payload for a single room, including last message and unread count."""
    members = [rm.user for rm in room.members]
    member_users = [_member_user_out(m) for m in members]

    my_membership = db.query(RoomMember).filter(
        RoomMember.room_id == room.id, RoomMember.user_id == user_id
    ).first()

    last_message = (
        db.query(Message)
        .filter(Message.room_id == room.id, Message.deleted_at.is_(None))
        .order_by(Message.created_at.desc())
        .first()
    )
    last_message_out = None
    if last_message and last_message.sender:
        last_message_out = {
            "id": last_message.id,
            "content": last_message.content,
            "created_at": last_message.created_at,
            "sender": _member_user_out(last_message.sender),
        }

    unread_count = 0
    if my_membership:
        if my_membership.last_read_at:
            unread_count = (
                db.query(Message)
                .filter(
                    Message.room_id == room.id,
                    Message.sender_id != user_id,
                    Message.created_at > my_membership.last_read_at,
                    Message.deleted_at.is_(None),
                )
                .count()
            )
        else:
            # First time opening the room: everything sent by others is unread.
            unread_count = (
                db.query(Message)
                .filter(
                    Message.room_id == room.id,
                    Message.sender_id != user_id,
                    Message.deleted_at.is_(None),
                )
                .count()
            )

    name = room.name
    avatar_url = None
    if room.type == RoomType.DIRECT and members:
        # Find the other participant for a direct room.
        other = next((m for m in members if m.id != user_id), members[0])
        name = other.full_name
        avatar_url = other.avatar_url

    return RoomOut(
        id=room.id,
        name=name,
        type=room.type,
        avatar_url=avatar_url,
        members=member_users,
        last_message=last_message_out,
        unread_count=unread_count,
        updated_at=room.updated_at,
    )


@router.get("", response_model=List[RoomOut])
def list_rooms(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """Return all rooms the current user is a member of."""
    user_id = payload.get("sub")
    rooms = (
        db.query(Room)
        .join(RoomMember, Room.id == RoomMember.room_id)
        .filter(RoomMember.user_id == user_id)
        .order_by(Room.updated_at.desc())
        .options(joinedload(Room.members).joinedload(RoomMember.user))
        .all()
    )
    return [_build_room_out(db, room, user_id) for room in rooms]


def _require_room_member(db: Session, room_id: str, user_id: str) -> Room:
    """Fetch a room and ensure the current user is a member."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oda bulunamadı.")
    is_member = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
        .first()
    )
    if not is_member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu odaya erişim yetkiniz yok.")
    return room


def _message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        room_id=message.room_id,
        content=message.content,
        message_type=message.message_type,
        created_at=message.created_at,
        edited_at=message.edited_at,
        sender=_member_user_out(message.sender),
        attachments=[],
    )


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    payload_token: dict = Depends(get_current_user_payload),
):
    """Create a new DIRECT or GROUP room.

    - DIRECT: requires exactly one other user id in member_ids. Returns existing room if any.
    - GROUP: requires a name and at least two member_ids.
    """
    user_id = payload_token.get("sub")
    member_ids = set(payload.member_ids)

    if payload.type == RoomType.DIRECT:
        if len(member_ids) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="DIRECT oda oluşturmak için tam olarak bir kullanıcı belirtmelisiniz.",
            )
        other_id = member_ids.pop()
        if other_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kendinizle direkt oda oluşturamazsınız.",
            )
        other = db.query(User).filter(User.id == other_id, User.is_active.is_(True)).first()
        if not other:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı veya pasif.")
        a_id, b_id = sorted([user_id, other_id])
        existing = (
            db.query(Room)
            .filter(
                Room.type == RoomType.DIRECT,
                Room.direct_user_a_id == a_id,
                Room.direct_user_b_id == b_id,
            )
            .first()
        )
        if existing:
            return _build_room_out(db, existing, user_id)

        try:
            room = Room(
                type=RoomType.DIRECT,
                created_by_id=user_id,
                direct_user_a_id=a_id,
                direct_user_b_id=b_id,
            )
            db.add(room)
            db.flush()
            db.add(RoomMember(room_id=room.id, user_id=user_id))
            db.add(RoomMember(room_id=room.id, user_id=other_id))
            db.commit()
            db.refresh(room)
            # Existing sockets only join rooms known at connect time. Add both
            # participants immediately so the first message arrives without F5.
            await join_user_to_room(user_id, room.id)
            await join_user_to_room(other_id, room.id)
            return _build_room_out(db, room, user_id)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.error("Failed to create direct room: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu kullanıcı ile zaten bir direkt oda bulunuyor.",
            )

    # GROUP
    if not payload.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GROUP oda için bir ad gereklidir.",
        )
    if user_id not in member_ids:
        member_ids.add(user_id)
    if len(member_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GROUP oda en az iki üye gerektirir.",
        )
    active_user_count = db.query(User).filter(User.id.in_(member_ids), User.is_active.is_(True)).count()
    if active_user_count != len(member_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grup üyelerinden biri bulunamadı veya pasif.",
        )

    room = Room(
        name=payload.name,
        type=RoomType.GROUP,
        created_by_id=user_id,
    )
    db.add(room)
    db.flush()
    for mid in member_ids:
        db.add(RoomMember(room_id=room.id, user_id=mid))
    db.commit()
    db.refresh(room)
    for member_id in member_ids:
        await join_user_to_room(member_id, room.id)
    logger.info("Group room created: %s by %s", room.id, user_id)
    return _build_room_out(db, room, user_id)


@router.get("/{room_id}/messages", response_model=MessageListOut)
def list_messages(
    room_id: str,
    limit: int = 30,
    before_id: str = "",
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """Return paginated message history for a room.

    Set `before_id` to load older messages than the given id.
    """
    user_id = payload.get("sub")
    _require_room_member(db, room_id, user_id)
    limit = max(1, min(limit, 100))

    query = db.query(Message).filter(Message.room_id == room_id, Message.deleted_at.is_(None))
    if before_id:
        before = db.query(Message).filter(Message.id == before_id).first()
        if before:
            query = query.filter(Message.created_at < before.created_at)
    messages = (
        query.options(joinedload(Message.sender))
        .order_by(Message.created_at.desc())
        .limit(limit + 1)
        .all()
    )

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]
    messages = list(reversed(messages))

    next_cursor = messages[0].id if has_more and messages else None
    return MessageListOut(
        messages=[_message_out(m) for m in messages],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post("/{room_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def create_message(
    room_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(get_current_user_payload),
):
    """Create a new text message in a room. sender_id is always taken from the token.

    The persisted message is also broadcast over Socket.IO so active room members
    receive it in real time without duplicating the sender's own copy.
    """
    user_id = token_payload.get("sub")
    _require_room_member(db, room_id, user_id)

    content = payload.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mesaj içeriği boş olamaz.",
        )

    message = Message(
        room_id=room_id,
        sender_id=user_id,
        content=content,
        message_type=MessageType.TEXT,
    )
    db.add(message)
    db.flush()

    # Update room timestamp and optionally bump the sender's read marker.
    room = db.query(Room).filter(Room.id == room_id).first()
    if room:
        room.updated_at = datetime.utcnow()
    membership = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
        .first()
    )
    if membership:
        membership.last_read_message_id = message.id
        membership.last_read_at = datetime.utcnow()

    db.commit()
    db.refresh(message)
    logger.info("Message %s created in room %s by %s", message.id, room_id, user_id)
    out = _message_out(message)
    await sio.emit("new_message", out, room=room_id)
    return out


@router.post("/{room_id}/read")
def mark_read(
    room_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """Mark messages in a room up to the given message id as read."""
    user_id = payload.get("sub")
    _require_room_member(db, room_id, user_id)
    message = db.query(Message).filter(Message.id == message_id, Message.room_id == room_id).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesaj bulunamadı.")
    membership = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
        .first()
    )
    if membership:
        membership.last_read_message_id = message_id
        membership.last_read_at = datetime.utcnow()
        db.commit()
    return {"ok": True}


@router.post("/{room_id}/members", response_model=RoomOut)
def add_member(
    room_id: str,
    user_id_to_add: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """Add a user to a group room. Only the creator or admins can manage members."""
    user_id = payload.get("sub")
    room = _require_room_member(db, room_id, user_id)
    if room.type != RoomType.GROUP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Üye yönetimi sadece grup odalarında yapılabilir.",
        )
    if room.created_by_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sadece oda oluşturucusu üye ekleyebilir.",
        )
    existing = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id, RoomMember.user_id == user_id_to_add)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kullanıcı zaten odanın üyesi.",
        )
    db.add(RoomMember(room_id=room_id, user_id=user_id_to_add))
    db.commit()
    db.refresh(room)
    return _build_room_out(db, room, user_id)


@router.delete("/{room_id}/members/{user_id_to_remove}")
def remove_member(
    room_id: str,
    user_id_to_remove: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """Remove a user from a group room. Only the creator can remove members."""
    user_id = payload.get("sub")
    room = _require_room_member(db, room_id, user_id)
    if room.type != RoomType.GROUP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Üye yönetimi sadece grup odalarında yapılabilir.",
        )
    if room.created_by_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sadece oda oluşturucusu üye çıkarabilir.",
        )
    membership = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id, RoomMember.user_id == user_id_to_remove)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Üye bulunamadı.")
    db.delete(membership)
    db.commit()
    return {"ok": True}
