"""
Real-time team chat router using FastAPI WebSockets.

All connected research desk clients receive instant broadcasts. Messages are
persisted to the chat_messages table so new joiners can load recent history.
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import ChatMessage, User
from app.schemas import ChatMessageOut, ChatUserOut
from app.security import decode_access_token, get_current_user_payload
from app.socketio_server import is_user_online
from app.websocket.manager import manager

logger = logging.getLogger("slayz.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])


def _decode_ws_user(token: str) -> dict:
    """Validate the bearer token supplied in the WebSocket query string."""
    if not token:
        raise ValueError("Missing token")
    return decode_access_token(token)


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """Main WebSocket endpoint for the research desk chat room."""
    token = websocket.query_params.get("token")
    try:
        payload = _decode_ws_user(token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("WebSocket auth failed: %s", exc)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload.get("sub")
    await manager.connect(websocket, user_id=user_id)

    db = SessionLocal()

    # Resolve the display name from the users table (JWT only carries the id).
    user_row = db.query(User).filter(User.id == user_id).first()
    display_name = (user_row.full_name if user_row else None) or payload.get("full_name") or user_id

    # Broadcast a subtle "user joined" system message with presence info.
    await manager.broadcast({
        "type": "system",
        "event": "user_joined",
        "sender_id": user_id,
        "sender_name": display_name,
        "online_user_ids": manager.online_user_ids(),
    })
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Geçersiz JSON"}))
                continue

            # Some clients may send already-stringified JSON; unwrap once if needed.
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({"type": "error", "detail": "Geçersiz JSON içeriği."}))
                    continue

            msg_type = data.get("type", "message") if isinstance(data, dict) else "message"
            content = ((data.get("content") if isinstance(data, dict) else "") or "").strip()
            article_id = data.get("article_id") if isinstance(data, dict) else None
            article_title = data.get("article_title") if isinstance(data, dict) else None
            ticker = data.get("ticker") if isinstance(data, dict) else None
            recipient_id = data.get("recipient_id") if isinstance(data, dict) else None

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if msg_type == "message" and not content:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Boş mesaj gönderilemez."}))
                continue

            # Persist and route the message: DM to a specific user, or team room broadcast.
            chat_message = ChatMessage(
                sender_id=user_id,
                sender_name=display_name,
                recipient_id=recipient_id,
                content=content,
                article_id=article_id,
                article_title=article_title,
                ticker=ticker,
            )
            db.add(chat_message)
            db.commit()
            db.refresh(chat_message)

            outgoing = {
                "type": "chat",
                "id": chat_message.id,
                "sender_id": chat_message.sender_id,
                "sender_name": chat_message.sender_name,
                "recipient_id": chat_message.recipient_id,
                "content": chat_message.content,
                "article_id": chat_message.article_id,
                "article_title": chat_message.article_title,
                "ticker": chat_message.ticker,
                "created_at": chat_message.created_at.isoformat(),
            }

            if recipient_id:
                # True user-to-user routing: deliver only to recipient + echo to sender.
                await manager.send_to_user(recipient_id, outgoing)
                await manager.send_to_user(user_id, outgoing)
            else:
                await manager.broadcast(outgoing)
    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected for user %s", user_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Chat WebSocket error for user %s: %s", user_id, exc, exc_info=True)
    finally:
        manager.disconnect(websocket)
        db.close()


@router.get("/users", response_model=List[ChatUserOut])
def list_chat_users(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """List registered workspace members for the desk chat roster.

    Includes presence (online sockets) and the last message exchanged with
    the requesting user for WhatsApp-style conversation previews.
    """
    me = payload.get("sub")
    users = (
        db.query(User)
        .filter(User.is_active.is_(True), User.id != me)
        .order_by(User.full_name.asc())
        .all()
    )

    result: List[ChatUserOut] = []
    for user in users:
        last_msg = (
            db.query(ChatMessage)
            .filter(
                or_(
                    and_(ChatMessage.sender_id == me, ChatMessage.recipient_id == user.id),
                    and_(ChatMessage.sender_id == user.id, ChatMessage.recipient_id == me),
                )
            )
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        result.append(
            ChatUserOut(
                id=user.id,
                full_name=user.full_name,
                role=user.role.value if hasattr(user.role, "value") else str(user.role),
                avatar_url=user.avatar_url,
                status=user.status.value if hasattr(user.status, "value") else (user.status or "available"),
                is_online=is_user_online(user.id),
                last_message=last_msg.content if last_msg else None,
                last_message_at=last_msg.created_at if last_msg else None,
            )
        )
    return result


@router.get("/history", response_model=List[ChatMessageOut])
def get_chat_history(
    limit: int = Query(100, le=500),
    peer_id: Optional[str] = Query(None, description="Return DM history with this user; omit for the team room"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """Return persisted chat history.

    - With peer_id: the private DM thread between the requester and that user.
    - Without peer_id: the shared team room (messages with no recipient).
    """
    me = payload.get("sub")
    query = db.query(ChatMessage)
    if peer_id:
        query = query.filter(
            or_(
                and_(ChatMessage.sender_id == me, ChatMessage.recipient_id == peer_id),
                and_(ChatMessage.sender_id == peer_id, ChatMessage.recipient_id == me),
            )
        )
    else:
        query = query.filter(ChatMessage.recipient_id.is_(None))

    messages = query.order_by(ChatMessage.created_at.desc()).limit(limit).all()
    return list(reversed(messages))
