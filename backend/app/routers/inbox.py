"""User-specific internal inbox endpoints for structured team notes."""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InboxMessage, User
from app.schemas import InboxMessageCreate, InboxMessageOut
from app.security import get_current_user_payload
from app.socketio_server import sio

logger = logging.getLogger("slayz.inbox")
router = APIRouter(prefix="/api/inbox", tags=["inbox"])


def _owned_message(db: Session, message_id: str, user_id: str) -> InboxMessage:
    message = (
        db.query(InboxMessage)
        .filter(InboxMessage.id == message_id, InboxMessage.recipient_id == user_id)
        .first()
    )
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesaj bulunamadı.")
    return message


@router.get("", response_model=List[InboxMessageOut])
def list_inbox_messages(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    user_id = payload.get("sub")
    query = (
        db.query(InboxMessage)
        .filter(InboxMessage.recipient_id == user_id)
        .order_by(InboxMessage.created_at.desc())
    )
    if unread_only:
        query = query.filter(InboxMessage.is_read.is_(False))
    return query.limit(100).all()


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    user_id = payload.get("sub")
    count = (
        db.query(InboxMessage)
        .filter(InboxMessage.recipient_id == user_id, InboxMessage.is_read.is_(False))
        .count()
    )
    return {"unread_count": count}


@router.post("", response_model=InboxMessageOut, status_code=status.HTTP_201_CREATED)
async def create_inbox_message(
    request: InboxMessageCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    sender_id = payload.get("sub")
    sender = db.query(User).filter(User.id == sender_id, User.is_active.is_(True)).first()
    recipient = (
        db.query(User)
        .filter(User.id == request.recipient_id, User.is_active.is_(True))
        .first()
    )
    if not sender:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Gönderen kullanıcı bulunamadı.")
    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alıcı kullanıcı bulunamadı.")
    if recipient.id == sender.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kendinize gelen kutusu mesajı gönderemezsiniz.")

    message = InboxMessage(
        sender_id=sender.id,
        recipient_id=recipient.id,
        sender_name=sender.full_name,
        sender_avatar=sender.avatar_url,
        title=request.title.strip(),
        content=request.content.strip(),
        associated_ticker=request.associated_ticker.strip().upper() if request.associated_ticker else None,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    await sio.emit(
        "inbox_message",
        {
            "id": message.id,
            "sender_name": message.sender_name,
            "title": message.title,
            "created_at": message.created_at.isoformat() if message.created_at else None,
        },
        room=f"user:{recipient.id}",
    )
    logger.info("Inbox message %s sent from %s to %s", message.id, sender.id, recipient.id)
    return message


@router.post("/{message_id}/read", response_model=InboxMessageOut)
def mark_as_read(
    message_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    message = _owned_message(db, message_id, payload.get("sub"))
    message.is_read = True
    db.commit()
    db.refresh(message)
    return message


@router.post("/mark-all-read")
def mark_all_as_read(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    user_id = payload.get("sub")
    (
        db.query(InboxMessage)
        .filter(InboxMessage.recipient_id == user_id, InboxMessage.is_read.is_(False))
        .update({InboxMessage.is_read: True}, synchronize_session=False)
    )
    db.commit()
    return {"detail": "Tüm mesajlar okundu olarak işaretlendi."}
