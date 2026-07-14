"""
SMTP email automation. Sends the AI-curated article to the Research team
with a link into the Web UI for Approve ("Paylaşmaya Değer") / Reject ("Değmez").
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import get_settings
from app.models import Article

logger = logging.getLogger("slayz.email")
settings = get_settings()


def _build_html(article: Article) -> str:
    review_url = f"{settings.frontend_base_url}/article/{article.id}"
    category_label = {
        "crypto": "Kripto Para",
        "stocks": "Borsa",
        "commodities": "Emtia / Altın",
        "general": "Genel",
    }.get(article.category.value if hasattr(article.category, "value") else article.category, "Genel")

    return f"""
    <html>
      <body style="font-family: 'Inter', 'DM Sans', Arial, sans-serif; background:#FFFFFF; color:#1E293B; padding: 24px;">
        <div style="max-width:600px;margin:0 auto;border:1px solid #F3F4F6;border-radius:16px;overflow:hidden;">
          <div style="background:#1E293B;padding:20px 28px;">
            <h2 style="color:#FFFFFF;margin:0;font-weight:600;">Slayz Haber Otomasyonu</h2>
          </div>
          <div style="padding:28px;">
            <span style="display:inline-block;background:#F3F4F6;color:#1E293B;font-size:12px;padding:4px 10px;border-radius:999px;font-weight:600;">
              {category_label}
            </span>
            <h1 style="font-size:22px;margin:16px 0 8px 0;">{article.ai_title or article.raw_title}</h1>
            <p style="font-size:15px;line-height:1.6;color:#334155;">
              {(article.ai_summary or '')[:500]}...
            </p>
            <div style="margin-top:28px;">
              <a href="{review_url}?action=approve" style="background:#16A34A;color:#fff;text-decoration:none;
                 padding:12px 22px;border-radius:10px;font-weight:600;margin-right:12px;display:inline-block;">
                Paylaşmaya Değer
              </a>
              <a href="{review_url}?action=reject" style="background:#DC2626;color:#fff;text-decoration:none;
                 padding:12px 22px;border-radius:10px;font-weight:600;display:inline-block;">
                Değmez
              </a>
            </div>
            <p style="margin-top:24px;font-size:12px;color:#94A3B8;">
              Bu haberi incelemek için <a href="{review_url}" style="color:#1E293B;">Web UI</a>'yi ziyaret edin.
            </p>
          </div>
        </div>
      </body>
    </html>
    """


def send_article_for_review(article: Article) -> bool:
    """Sends the curated article to the research team. Returns True on success."""
    recipients = settings.research_team_email_list
    if not recipients:
        logger.warning("No RESEARCH_TEAM_EMAILS configured, skipping email for article %s", article.id)
        return False

    if not settings.smtp_username or not settings.smtp_password:
        logger.error("SMTP credentials not configured; cannot send email for article %s", article.id)
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = f"[Slayz Haber] {article.ai_title or article.raw_title}"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_username}>"
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(_build_html(article), "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_username, recipients, message.as_string())
        logger.info("Review email sent for article %s to %s", article.id, recipients)
        return True
    except smtplib.SMTPException as exc:
        logger.error("Failed to send review email for article %s: %s", article.id, exc, exc_info=True)
        return False


def _build_share_html(article: Article, note: Optional[str]) -> str:
    review_url = f"{settings.frontend_base_url}/article/{article.id}"
    category_label = {
        "crypto": "Kripto Para",
        "stocks": "Borsa",
        "commodities": "Emtia / Altın",
        "general": "Genel",
    }.get(article.category.value if hasattr(article.category, "value") else article.category, "Genel")

    note_html = (
        f"""
        <div style="margin-top:16px;padding:14px 16px;background:#F8FAFC;border-left:3px solid #1E293B;border-radius:8px;">
          <p style="margin:0;font-size:13px;color:#475569;"><strong>Not:</strong> {note}</p>
        </div>
        """
        if note
        else ""
    )

    return f"""
    <html>
      <body style="font-family: 'Inter', 'DM Sans', Arial, sans-serif; background:#FFFFFF; color:#1E293B; padding: 24px;">
        <div style="max-width:600px;margin:0 auto;border:1px solid #F3F4F6;border-radius:16px;overflow:hidden;">
          <div style="background:#1E293B;padding:20px 28px;">
            <h2 style="color:#FFFFFF;margin:0;font-weight:600;">Slayz Haber Otomasyonu</h2>
            <p style="color:#94A3B8;margin:4px 0 0 0;font-size:13px;">Bir ekip arkadaşınız sizinle bir haber paylaştı</p>
          </div>
          <div style="padding:28px;">
            <span style="display:inline-block;background:#F3F4F6;color:#1E293B;font-size:12px;padding:4px 10px;border-radius:999px;font-weight:600;">
              {category_label}
            </span>
            <h1 style="font-size:22px;margin:16px 0 8px 0;">{article.ai_title or article.raw_title}</h1>
            <p style="font-size:15px;line-height:1.6;color:#334155;">
              {(article.ai_summary or '')[:800]}
            </p>
            {note_html}
            <div style="margin-top:28px;">
              <a href="{review_url}" style="background:#1E293B;color:#fff;text-decoration:none;
                 padding:12px 22px;border-radius:10px;font-weight:600;display:inline-block;">
                Haberi Görüntüle
              </a>
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def send_shared_article(article: Article, recipient_email: str, note: Optional[str] = None) -> bool:
    """Sends a curated article to an arbitrary teammate email. Returns True on success."""
    if not settings.smtp_username or not settings.smtp_password:
        logger.error("SMTP credentials not configured; cannot share article %s", article.id)
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = f"[Slayz Haber] {article.ai_title or article.raw_title}"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_username}>"
    message["To"] = recipient_email
    message.attach(MIMEText(_build_share_html(article, note), "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_username, [recipient_email], message.as_string())
        logger.info("Shared article %s emailed to %s", article.id, recipient_email)
        return True
    except smtplib.SMTPException as exc:
        logger.error("Failed to share article %s to %s: %s", article.id, recipient_email, exc, exc_info=True)
        return False
