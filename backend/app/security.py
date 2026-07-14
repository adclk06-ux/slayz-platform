"""
Security utilities: password hashing, JWT issuing/verification, RBAC dependencies,
and a Fernet-based field encryptor for encrypting sensitive data at rest.
"""
import base64
import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

logger = logging.getLogger("slayz.security")
settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {"sub": subject, "role": role, "type": "access", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(days=settings.refresh_token_expire_days))
    payload = {"sub": subject, "type": "refresh", "jti": str(uuid.uuid4()), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama bilgisi geçersiz veya süresi dolmuş.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        logger.warning("Refresh token decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum bilgisi geçersiz veya süresi dolmuş.",
        )
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz refresh token.",
        )
    return payload


async def get_current_user_payload(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama bilgisi geçersiz veya süresi dolmuş.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(token)


async def optional_current_user_payload(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[dict]:
    """Returns the decoded JWT payload when a valid token is supplied.

    In debug/development mode, missing or invalid tokens are tolerated so the
    local workspace UI keeps working across backend restarts. In production
    (debug=False) this behaves like a normal optional auth dependency.
    """
    if not token:
        return None
    try:
        return decode_access_token(token)
    except HTTPException:
        if settings.debug:
            logger.debug("Optional auth: ignoring invalid token in debug mode")
            return None
        raise


def require_roles(*allowed_roles: Role):
    """RBAC dependency factory. Usage: Depends(require_roles(Role.ADMIN, Role.ANALYST))"""

    async def _dependency(payload: dict = Depends(get_current_user_payload)) -> dict:
        role = payload.get("role")
        if role not in [r.value for r in allowed_roles]:
            logger.warning("RBAC denied: user=%s role=%s required=%s", payload.get("sub"), role, allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için yetkiniz bulunmamaktadır.",
            )
        return payload

    return _dependency


# ---------------------------------------------------------------------------
# Field-level encryption (encryption at rest for sensitive columns)
# ---------------------------------------------------------------------------
def _derive_fernet_key(raw_key: str) -> bytes:
    """Derive a valid 32-byte urlsafe base64 Fernet key from an arbitrary secret string."""
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key_source = settings.db_encryption_key or settings.app_secret_key
        _fernet = Fernet(_derive_fernet_key(key_source))
    return _fernet


def encrypt_value(value: str) -> str:
    if value is None:
        return value
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str) -> str:
    if value is None:
        return value
    try:
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt field value - invalid token/key mismatch.")
        return ""
