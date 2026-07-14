"""
Simple in-memory WebSocket connection manager for real-time broadcasts.

Designed for a single FastAPI process (typical local/dev deployment). For
multi-server production deployments this should be backed by Redis Pub/Sub
or a similar broker.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from starlette.websockets import WebSocket

logger = logging.getLogger("slayz.websocket")


class ConnectionManager:
    """Keeps track of active WebSocket clients and broadcasts messages.

    Connections can optionally be registered under a user_id, enabling true
    user-to-user direct message routing for the workspace desk chat.
    """

    def __init__(self):
        self._connections: List[WebSocket] = []
        self._user_connections: Dict[str, List[WebSocket]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        if user_id:
            self._user_connections.setdefault(user_id, []).append(websocket)
        logger.info("WebSocket client connected. Total: %d", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)
        for user_id, sockets in list(self._user_connections.items()):
            if websocket in sockets:
                sockets.remove(websocket)
            if not sockets:
                del self._user_connections[user_id]
        logger.info("WebSocket client disconnected. Total: %d", len(self._connections))

    def online_user_ids(self) -> List[str]:
        """Return the ids of all users with at least one live socket."""
        return list(self._user_connections.keys())

    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> bool:
        """Send a JSON message to every socket registered for one user.

        Returns True if at least one socket received the message.
        """
        sockets = self._user_connections.get(user_id, [])
        if not sockets:
            return False
        text = json.dumps(message, ensure_ascii=False, default=str)
        delivered = False
        stale: List[WebSocket] = []
        for connection in sockets:
            try:
                await connection.send_text(text)
                delivered = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to send direct message to %s: %s", user_id, exc)
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)
        return delivered

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Send a JSON message to every connected client.

        Failed sends are logged but do not break the loop, so one stale
        connection cannot stop the broadcast.
        """
        text = json.dumps(message, ensure_ascii=False, default=str)
        stale: List[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_text(text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to send WebSocket message: %s", exc)
                stale.append(connection)

        for connection in stale:
            self.disconnect(connection)

    def broadcast_sync(self, message: Dict[str, Any]) -> None:
        """Thread-safe helper for synchronous callers (e.g. APScheduler jobs).

        Schedules the async broadcast on the configured event loop. If no loop
        is available, falls back to creating a transient one, which is acceptable
        only in development/testing.
        """
        if self._loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to schedule broadcast on loop: %s", exc)

        # Fallback: create a temporary event loop for this thread.
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.broadcast(message))
        finally:
            loop.close()
            asyncio.set_event_loop(None)


manager = ConnectionManager()
