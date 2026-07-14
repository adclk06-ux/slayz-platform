"""Administrator-only workspace user management endpoints."""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.auth import normalize_org_email
from app.schemas import UserCreate, UserOut, UserUpdate
from app.security import Role, hash_password, require_roles

logger = logging.getLogger("slayz.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles(Role.ADMIN)),
):
    return db.query(User).order_by(User.is_active.desc(), User.full_name.asc()).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_roles(Role.ADMIN)),
):
    email = normalize_org_email(str(payload.email))
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta zaten kayıtlı.")
    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Admin %s created user %s", admin.get("sub"), user.email)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_roles(Role.ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı.")
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.role is not None:
        user.role = payload.role
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    if payload.is_active is not None:
        if user.id == admin.get("sub") and not payload.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kendi yönetici hesabınızı devre dışı bırakamazsınız.",
            )
        user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    logger.info("Admin %s updated user %s", admin.get("sub"), user.email)
    return user


@router.delete("/users/{user_id}", response_model=UserOut)
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_roles(Role.ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı.")
    if user.id == admin.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kendi yönetici hesabınızı devre dışı bırakamazsınız.",
        )
    user.is_active = False
    db.commit()
    db.refresh(user)
    logger.info("Admin %s deactivated user %s", admin.get("sub"), user.email)
    return user
