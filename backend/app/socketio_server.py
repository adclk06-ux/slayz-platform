"""Authenticated Socket.IO server for room chat, presence and inbox alerts."""
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qs

import socketio

from app.config import get_settings
from app.database import SessionLocal
from app.models import Message, MessageType, Room, RoomMember, User, UserStatus
from app.security import decode_access_token

logger = logging.getLogger("slayz.socketio")
settings = get_settings()

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.socketio_cors_origins,
    logger=settings.debug,
    engineio_logger=settings.debug,
)

_sid_to_user: dict[str, str] = {}
_user_to_sids: dict[str, set[str]] = {}


def is_user_online(user_id: str) -> bool:
    return bool(_user_to_sids.get(user_id))


def online_user_ids() -> list[str]:
    return [user_id for user_id, sids in _user_to_sids.items() if sids]


def _extract_token(environ: dict, auth: Optional[dict]) -> Optional[str]:
    # Prefer Socket.IO auth payload so JWTs are not written into request URLs/logs.
    if isinstance(auth, dict) and auth.get("token"):
        return str(auth["token"])
    qs = parse_qs(environ.get("QUERY_STRING", ""))
    return qs.get("token", [None])[0]


def _member_user_out(user: User) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "status": user.status.value if user.status else UserStatus.AVAILABLE.value,
        "is_online": is_user_online(user.id),
    }


def _message_out(message: Message) -> dict:
    return {
        "id": message.id,
        "room_id": message.room_id,
        "content": message.content,
        "message_type": message.message_type.value,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
        "sender": _member_user_out(message.sender),
        "attachments": [],
    }


async def _broadcast_presence(user_id: str, is_online: bool) -> None:
    await sio.emit(
        "presence",
        {"user_id": user_id, "is_online": is_online, "last_seen_at": datetime.utcnow().isoformat()},
    )


@sio.event
async def connect(sid: str, environ: dict, auth: Optional[dict] = None):
    token = _extract_token(environ, auth)
    if not token:
        raise ConnectionRefusedError("Kimlik doğrulama bilgisi eksik.")
    try:
        payload = decode_access_token(token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Socket connection rejected for sid=%s: %s", sid, exc)
        raise ConnectionRefusedError("Geçersiz veya süresi dolmuş oturum.") from exc

    user_id = payload.get("sub")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
        if not user:
            raise ConnectionRefusedError("Kullanıcı bulunamadı veya pasif.")
        room_ids = [
            row[0]
            for row in db.query(RoomMember.room_id).filter(RoomMember.user_id == user_id).all()
        ]
        user.status = UserStatus.ONLINE
        user.last_seen_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

    _sid_to_user[sid] = user_id
    _user_to_sids.setdefault(user_id, set()).add(sid)
    await sio.enter_room(sid, f"user:{user_id}")
    for room_id in room_ids:
        await sio.enter_room(sid, room_id)
    await _broadcast_presence(user_id, True)
    logger.info("Socket connected: sid=%s user=%s rooms=%d", sid, user_id, len(room_ids))


@sio.event
async def disconnect(sid: str):
    user_id = _sid_to_user.pop(sid, None)
    if not user_id:
        return
    sids = _user_to_sids.get(user_id)
    if sids:
        sids.discard(sid)
        if not sids:
            _user_to_sids.pop(user_id, None)
    if not is_user_online(user_id):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.status = UserStatus.OFFLINE
                user.last_seen_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        await _broadcast_presence(user_id, False)
    logger.info("Socket disconnected: sid=%s user=%s", sid, user_id)


def _is_member(db, room_id: str, user_id: str) -> bool:
    return (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
        .first()
        is not None
    )


@sio.event
async def join_room(sid: str, data: dict):
    user_id = _sid_to_user.get(sid)
    room_id = data.get("room_id") if isinstance(data, dict) else data
    if not user_id or not room_id:
        return {"ok": False}
    db = SessionLocal()
    try:
        allowed = _is_member(db, room_id, user_id)
    finally:
        db.close()
    if not allowed:
        return {"ok": False, "message": "Bu odaya erişim yetkiniz yok."}
    await sio.enter_room(sid, room_id)
    return {"ok": True}


@sio.event
async def leave_room(sid: str, data: dict):
    room_id = data.get("room_id") if isinstance(data, dict) else data
    if room_id:
        await sio.leave_room(sid, room_id)
    return {"ok": True}


@sio.event
async def send_message(sid: str, data: dict):
    user_id = _sid_to_user.get(sid)
    if not user_id or not isinstance(data, dict):
        return {"ok": False, "message": "Oturum bulunamadı."}
    room_id = data.get("room_id")
    content = str(data.get("content", "")).strip()
    if not room_id or not content:
        return {"ok": False, "message": "Mesaj içeriği boş olamaz."}
    if len(content) > 5000:
        return {"ok": False, "message": "Mesaj en fazla 5000 karakter olabilir."}

    db = SessionLocal()
    try:
        if not _is_member(db, room_id, user_id):
            return {"ok": False, "message": "Odaya erişim yetkiniz yok."}
        message = Message(
            room_id=room_id,
            sender_id=user_id,
            content=content,
            message_type=MessageType.TEXT,
        )
        db.add(message)
        db.flush()
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
        out = _message_out(message)
    finally:
        db.close()

    await sio.emit("new_message", out, room=room_id)
    return {"ok": True, "message": out}


@sio.event
async def typing(sid: str, data: dict):
    user_id = _sid_to_user.get(sid)
    if not user_id or not isinstance(data, dict):
        return {"ok": False}
    room_id = data.get("room_id")
    if not room_id:
        return {"ok": False}
    db = SessionLocal()
    try:
        allowed = _is_member(db, room_id, user_id)
    finally:
        db.close()
    if not allowed:
        return {"ok": False}
    await sio.emit(
        "typing",
        {"room_id": room_id, "user_id": user_id, "is_typing": bool(data.get("is_typing"))},
        room=room_id,
        skip_sid=sid,
    )
    return {"ok": True}


@sio.event
async def mark_read(sid: str, data: dict):
    user_id = _sid_to_user.get(sid)
    if not user_id or not isinstance(data, dict):
        return {"ok": False}
    room_id = data.get("room_id")
    message_id = data.get("message_id")
    if not room_id or not message_id:
        return {"ok": False}

    db = SessionLocal()
    try:
        membership = (
            db.query(RoomMember)
            .filter(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
            .first()
        )
        message = db.query(Message).filter(Message.id == message_id, Message.room_id == room_id).first()
        if not membership or not message:
            return {"ok": False}
        membership.last_read_message_id = message_id
        membership.last_read_at = datetime.utcnow()
        db.commit()
        read_at = membership.last_read_at.isoformat()
    finally:
        db.close()

    await sio.emit(
        "read_receipt",
        {"room_id": room_id, "user_id": user_id, "message_id": message_id, "read_at": read_at},
        room=room_id,
        skip_sid=sid,
    )
    return {"ok": True}
