"""
Floating AI Assistant endpoint: a chat grounded in the articles currently on
the Research team's dashboard. Requires OPENAI_API_KEY to be configured;
returns a clear 503 (not a crash) when it isn't.
"""
import logging
import re
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from openai import OpenAIError

from app.llm.assistant import chat_with_assistant
from app.market.ticker_worker import TICKER_SYMBOLS
from app.models import Article, ArticleStatus
from app.rate_limit import limiter
from app.schemas import AssistantChatRequest, AssistantChatResponse
from app.security import get_current_user_payload

logger = logging.getLogger("slayz.assistant_router")
router = APIRouter(prefix="/api/assistant", tags=["assistant"])


def _build_dashboard_context(db: Session) -> str:
    articles = (
        db.query(Article)
        .filter(Article.status.in_([ArticleStatus.PENDING_REVIEW, ArticleStatus.APPROVED]))
        .order_by(Article.scraped_at.desc())
        .limit(15)
        .all()
    )
    lines = []
    for article in articles:
        title = article.ai_title or article.raw_title
        summary = (article.ai_summary or "")[:280]
        category = article.category.value if hasattr(article.category, "value") else article.category
        lines.append(f"- [{category}] {title}: {summary}")
    return "\n".join(lines)


# Available ticker symbols for quick regex intent matching.
_TICKER_SYMBOLS = {t["symbol"].upper() for t in TICKER_SYMBOLS}

# Friendly aliases for ambiguous user prompts.
_TICKER_ALIASES = {
    "BIST 100": "XU100",
    "BIST100": "XU100",
    "BIST 500": "XU500",
    "BIST500": "XU500",
    "BIST 50": "XU500",
    "BIST50": "XU500",
    "ALTIN": "XAUUSD",
    "ONS ALTIN": "XAUUSD",
    "GRAM ALTIN": "GRAMALTIN",
    "GRAMALTIN": "GRAMALTIN",
    "BITCOIN": "BTCUSD",
    "BTC": "BTCUSD",
    "ETHEREUM": "ETHUSD",
    "ETH": "ETHUSD",
    "TÜRK HAVA YOLLARI": "THYAO",
    "TURK HAVA YOLLARI": "THYAO",
    "EREĞLİ": "EREGL",
    "EREGLİ": "EREGL",
    "EREGLI": "EREGL",
    "TÜPRAŞ": "TUPRS",
    "TUPRAS": "TUPRS",
    "AKBANK": "AKBNK",
}


def _detect_ticker_intent(text: str) -> Optional[dict]:
    """Detect explicit routing requests like 'THYAO grafiğine götür'."""
    text_upper = text.upper()
    # Direct symbol match
    for symbol in sorted(_TICKER_SYMBOLS, key=len, reverse=True):
        if symbol in text_upper:
            return {"type": "focus_ticker", "symbol": symbol, "route": "/terminal"}
    # Alias match
    for alias, symbol in sorted(_TICKER_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in text_upper:
            return {"type": "focus_ticker", "symbol": symbol, "route": "/terminal"}
    # Generic chart intent
    if re.search(r"\b(GRAFİĞİNİ AÇ|GRAFİGİNİ AÇ|GRAFİK|CHART|FİYAT|FIYAT|NEREYE GİDİYOR|NASIL GİDİYOR)\b", text_upper):
        return {"type": "open_terminal", "route": "/terminal"}
    return None


@router.post("/chat", response_model=AssistantChatResponse)
@limiter.limit("15/minute")
def chat(
    request: Request,
    payload: AssistantChatRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user_payload),
):
    context = _build_dashboard_context(db)
    messages = [{"role": m.role, "content": m.content} for m in payload.messages]
    last_user_message = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    action = _detect_ticker_intent(last_user_message)

    try:
        reply = chat_with_assistant(messages, context)
    except (RuntimeError, OpenAIError) as exc:
        logger.warning("Assistant LLM unavailable, using fallback reply: %s", exc)
        if action:
            friendly = next((t["name"] for t in TICKER_SYMBOLS if t["symbol"] == action.get("symbol")), "terminal")
            return AssistantChatResponse(
                reply=f"{friendly} grafiğini Slayz Terminal'de açıyorum. AI analizleri için OPENAI_API_KEY tanımlanması gerekiyor.",
                action=action,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI asistanı henüz yapılandırılmadı. Lütfen OPENAI_API_KEY tanımlayın.",
        )
    except Exception as exc:  # noqa: BLE001 - upstream/API failure, never fail silently
        logger.error("Assistant chat error: %s", exc, exc_info=True)
        if action:
            friendly = next((t["name"] for t in TICKER_SYMBOLS if t["symbol"] == action.get("symbol")), "terminal")
            return AssistantChatResponse(
                reply=f"{friendly} grafiğini Slayz Terminal'de açıyorum. Tam AI analizi için servis bağlantısını kontrol edin.",
                action=action,
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI asistanına şu anda ulaşılamıyor. Lütfen daha sonra tekrar deneyin.",
        )

    return AssistantChatResponse(reply=reply, action=action)
