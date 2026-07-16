"""Authenticated enterprise e-mail gateway endpoints."""
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import BriefingSnapshot
from app.security import get_current_user_payload

logger = logging.getLogger("slayz.mail")
router = APIRouter(prefix="/api/mail", tags=["mail"])


def _resolve_mail_api_key(settings) -> str:
    return os.getenv("MAIL_API_KEY") or settings.mail_api_key


class SendReportRequest(BaseModel):
    to: List[EmailStr]
    subject: str = Field(..., min_length=1, max_length=255)
    body_html: str = Field(..., min_length=1, max_length=200_000)
    body_text: Optional[str] = Field(default=None, max_length=200_000)
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None


class SendReportResponse(BaseModel):
    status: str
    provider: str
    recipients: int
    message_id: Optional[str] = None
    note: Optional[str] = None


class ReceiveWebhookPayload(BaseModel):
    provider: str = Field(..., description="resend | sendgrid")
    type: str = Field(..., description="delivery | bounce | complaint | open | click | inbound")
    email: Optional[str] = None
    message_id: Optional[str] = None
    timestamp: Optional[str] = None
    payload: Optional[dict] = None


def _send_resend(req: SendReportRequest, sender: str, api_key: str) -> str | None:
    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "from": sender,
            "to": [str(value) for value in req.to],
            "cc": [str(value) for value in (req.cc or [])],
            "bcc": [str(value) for value in (req.bcc or [])],
            "subject": req.subject,
            "html": req.body_html,
            "text": req.body_text or "",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Resend HTTP {response.status_code}: {response.text[:300]}")
    body = response.json() if response.content else {}
    return body.get("id")


def _send_sendgrid(req: SendReportRequest, sender: str, api_key: str) -> str | None:
    personalization = {
        "to": [{"email": str(value)} for value in req.to],
        "cc": [{"email": str(value)} for value in (req.cc or [])],
        "bcc": [{"email": str(value)} for value in (req.bcc or [])],
        "subject": req.subject,
    }
    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "personalizations": [personalization],
            "from": {"email": sender},
            "content": [
                {"type": "text/plain", "value": req.body_text or ""},
                {"type": "text/html", "value": req.body_html},
            ],
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"SendGrid HTTP {response.status_code}: {response.text[:300]}")
    return response.headers.get("X-Message-Id")


def _send_smtp(req: SendReportRequest, settings) -> str | None:
    message = EmailMessage()
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from}>" if settings.smtp_from_name else settings.smtp_from
    message["To"] = ", ".join(str(value) for value in req.to)
    if req.cc:
        message["Cc"] = ", ".join(str(value) for value in req.cc)
    message["Subject"] = req.subject
    message.set_content(req.body_text or "Bu mesaj HTML biçiminde hazırlanmıştır.")
    message.add_alternative(req.body_html, subtype="html")
    recipients = [str(value) for value in req.to + (req.cc or []) + (req.bcc or [])]

    smtp_cls = smtplib.SMTP_SSL if settings.smtp_port == 465 else smtplib.SMTP
    with smtp_cls(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_port != 465:
            server.ehlo()
            server.starttls()
            server.ehlo()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message, to_addrs=recipients)
    return message.get("Message-ID")


@router.post("/send-report", response_model=SendReportResponse)
def send_report(req: SendReportRequest, user: dict = Depends(get_current_user_payload)):
    """Send a message only when a real provider is fully configured."""
    settings = get_settings()
    provider = settings.mail_provider.lower().strip() if settings.mail_provider else ""
    api_key = _resolve_mail_api_key(settings)
    sender = settings.mail_default_from or settings.smtp_from
    recipients = req.to + (req.cc or []) + (req.bcc or [])
    if not recipients:
        raise HTTPException(status_code=400, detail="En az bir alıcı gereklidir.")

    try:
        if provider == "resend" and api_key and sender:
            message_id = _send_resend(req, sender, api_key)
        elif provider == "sendgrid" and api_key and sender:
            message_id = _send_sendgrid(req, sender, api_key)
        elif provider == "smtp" and settings.smtp_host and settings.smtp_from:
            if settings.smtp_username and not settings.smtp_password:
                raise RuntimeError("SMTP_PASSWORD eksik.")
            message_id = _send_smtp(req, settings)
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="E-posta sağlayıcısı yapılandırılmamış. MAIL_PROVIDER ve sağlayıcı bilgilerini ayarlayın.",
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Mail send failed provider=%s actor=%s: %s", provider, user.get("sub"), exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="E-posta sağlayıcısı mesajı gönderemedi.") from exc

    logger.info("Mail sent provider=%s actor=%s recipients=%d", provider, user.get("sub"), len(recipients))
    return SendReportResponse(status="sent", provider=provider, recipients=len(recipients), message_id=message_id)


@router.post("/webhook/{provider}")
def receive_webhook(
    provider: str,
    payload: ReceiveWebhookPayload,
    webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
):
    """Receive provider delivery/inbound events; protect with MAIL_WEBHOOK_SECRET."""
    settings = get_settings()
    if settings.mail_webhook_secret and webhook_secret != settings.mail_webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook doğrulaması başarısız.")
    logger.info("Received %s webhook: type=%s message_id=%s", provider, payload.type, payload.message_id)
    return {"status": "ok", "provider": provider, "type": payload.type}


class DispatchBriefRequest(BaseModel):
    slot: str = Field("08:00", pattern="^(08:00|16:00)$")
    recipients: Optional[List[EmailStr]] = None


@router.post("/dispatch-briefing", response_model=SendReportResponse)
def dispatch_briefing(
    req: DispatchBriefRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_payload),
):
    settings = get_settings()
    snapshot = db.query(BriefingSnapshot).filter(BriefingSnapshot.slot == req.slot).order_by(BriefingSnapshot.created_at.desc()).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"{req.slot} slotu için hazır brifing bulunamadı.")
    recipients = req.recipients or settings.research_team_email_list
    if not recipients:
        raise HTTPException(status_code=400, detail="RESEARCH_TEAM_EMAILS veya recipients alanı gereklidir.")
    label = "Sabah" if req.slot == "08:00" else "Akşam"
    return send_report(
        SendReportRequest(
            to=recipients,
            subject=f"Slayz {label} Brifi — {req.slot}",
            body_html=f"<h2>Slayz {label} Araştırma Brifi ({req.slot})</h2><p>{snapshot.summary}</p>",
            body_text=snapshot.summary,
        ),
        user=user,
    )


@router.get("/health")
def mail_health(_: dict = Depends(get_current_user_payload)):
    settings = get_settings()
    api_key = _resolve_mail_api_key(settings)
    provider = settings.mail_provider.lower().strip() if settings.mail_provider else "none"
    configured = (
        (provider in {"resend", "sendgrid"} and bool(api_key and settings.mail_default_from))
        or (provider == "smtp" and bool(settings.smtp_host and settings.smtp_from))
    )
    return {"provider": provider, "configured": configured, "default_from": settings.mail_default_from or settings.smtp_from}
