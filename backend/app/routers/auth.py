"""Authentication and first-run account setup endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User, UserRole, UserStatus
from app.schemas import LoginRequest, SetupStatusOut, TokenResponse, UserCreate, UserOut
from app.security import (
    Role,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user_payload,
    hash_password,
    require_roles,
    verify_password,
)

logger = logging.getLogger("slayz.auth")
settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])


def normalize_org_email(email: str) -> str:
    normalized = email.strip().lower()
    domain = settings.allowed_email_domain.strip().lower().lstrip("@")
    if normalized.rsplit("@", 1)[-1] != domain:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Yalnızca @{domain} uzantılı kurumsal e-posta adresleri kullanılabilir.",
        )
    return normalized


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    same_site = settings.cookie_samesite.lower()
    if same_site not in {"lax", "strict", "none"}:
        same_site = "lax"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.debug,
        samesite=same_site,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/api/auth",
    )


@router.get("/setup-status", response_model=SetupStatusOut)
def setup_status(db: Session = Depends(get_db)):
    return SetupStatusOut(
        needs_setup=db.query(User).count() == 0,
        allowed_email_domain=settings.allowed_email_domain,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        logger.warning("Failed login attempt for email=%s", email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-posta veya şifre hatalı.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hesabınız devre dışı bırakılmış.")

    access_token = create_access_token(subject=user.id, role=user.role.value)
    refresh_token = create_refresh_token(subject=user.id)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, role=user.role, full_name=user.full_name)


@router.post("/refresh", response_model=TokenResponse)
def refresh(response: Response, refresh_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum bilgisi eksik.")
    payload = decode_refresh_token(refresh_token)
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı bulunamadı veya pasif.")

    access_token = create_access_token(subject=user.id, role=user.role.value)
    new_refresh_token = create_refresh_token(subject=user.id)
    _set_refresh_cookie(response, new_refresh_token)
    return TokenResponse(access_token=access_token, role=user.role, full_name=user.full_name)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="refresh_token", path="/api/auth")
    return {"detail": "Çıkış yapıldı."}


@router.get("/me", response_model=UserOut)
def me(db: Session = Depends(get_db), payload: dict = Depends(get_current_user_payload)):
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı.")
    return user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles(Role.ADMIN)),
):
    """Create a workspace user. Only admins can register accounts."""
    email = normalize_org_email(str(payload.email))
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta zaten kayıtlı.")

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        status=UserStatus.AVAILABLE,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("New user registered by admin: %s (%s)", user.email, user.role)
    return user


@router.post("/bootstrap-admin", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: UserCreate, db: Session = Depends(get_db)):
    """One-time first-run setup. Disabled permanently after the first user exists."""
    if db.query(User).count() > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sistem zaten kurulmuş. İlk yönetici yalnızca boş veritabanında oluşturulabilir.",
        )
    email = normalize_org_email(str(payload.email))
    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        role=UserRole.ADMIN,
        status=UserStatus.AVAILABLE,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Bootstrap admin created: %s", user.email)
    return user
