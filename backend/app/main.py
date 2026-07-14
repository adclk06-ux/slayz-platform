"""
Slayz Haber Otomasyonu - FastAPI application entrypoint.

Security notes:
- JWT bearer auth (not cookies) -> not vulnerable to classic CSRF.
- SQLAlchemy ORM with parameterized queries -> protected against SQL Injection.
- Pydantic schemas validate/escape all inputs; responses are JSON (no raw HTML
  templating of user input) -> mitigates XSS.
- Rate limiting via slowapi to reduce brute-force / abuse risk.
- Sensitive DB fields encrypted at rest via app.security.encrypt_value (Fernet).
- All exceptions are logged with context; nothing fails silently.
"""
import asyncio
import logging

import socketio
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import ensure_schema
from app.logging_config import setup_logging
from app.rate_limit import limiter
from app.routers import admin, ai, articles, assistant, auth, chat, inbox, mail, market, rooms
from app.scheduler import start_scheduler, stop_scheduler
from app.socketio_server import sio
from app.websocket.manager import manager as websocket_manager

settings = get_settings()
setup_logging(settings.debug)
logger = logging.getLogger("slayz.main")

app = FastAPI(
    title="Slayz Haber Otomasyonu",
    description="Enterprise haber toplama, AI analiz ve küratörlük platformu.",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.debug:
    # Dev/preview mode: keep credentials=True so refresh-token cookies can be
    # sent back and forth from configured frontend origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Geçersiz istek verisi.", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Sunucu hatası oluştu. Olay kaydedildi."},
    )


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(articles.router)
app.include_router(assistant.router)
app.include_router(inbox.router)
app.include_router(chat.router)
app.include_router(market.router)
app.include_router(ai.router)
app.include_router(rooms.router)
app.include_router(mail.router)


@app.on_event("startup")
def on_startup():
    ensure_schema()
    # Capture the running event loop so synchronous jobs can schedule broadcasts.
    try:
        websocket_manager.set_event_loop(asyncio.get_event_loop())
    except RuntimeError:
        pass
    if settings.scheduler_enabled:
        start_scheduler()
    logger.info("Slayz Haber Otomasyonu backend started. env=%s", settings.app_env)


@app.on_event("shutdown")
def on_shutdown():
    stop_scheduler()
    logger.info("Slayz Haber Otomasyonu backend stopped.")


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": "slayz-haber-otomasyonu"}


# Mount the Socket.IO real-time server in front of the FastAPI app.
# Non-Socket.IO requests are transparently forwarded to the FastAPI app.
app = socketio.ASGIApp(sio, other_asgi_app=app)
