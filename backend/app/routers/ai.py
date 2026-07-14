"""Grounded asset analysis powered by OpenAI and server-side market facts."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.market.insights import compute_technical_context
from app.market.market_data import extract_quote_facts, fetch_history, fetch_quote_summary
from app.models import Article, MarketTicker
from app.security import get_current_user_payload

logger = logging.getLogger("slayz.ai")
router = APIRouter(prefix="/api/ai", tags=["ai"])


class PredictRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    question: Optional[str] = Field(default=None, max_length=500)
    # Kept for backwards compatibility. The server fetches its own market data.
    history_points: Optional[List[dict]] = Field(default=None, max_length=500)
    news_headlines: Optional[List[str]] = Field(default=None, max_length=20)


class PredictResponse(BaseModel):
    symbol: str
    prediction: str
    summary: str
    stance: str
    sentiment: str
    confidence: str
    technical_view: str
    catalysts: List[str]
    risks: List[str]
    data_quality: str
    metrics: Dict[str, Any]
    reasoning: Optional[str] = None
    disclaimer: str
    generated_at: datetime


def _clean_list(value: Any, limit: int = 5) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:limit]


def _recent_news(db: Session, symbol: str, company_name: str) -> List[str]:
    rows = (
        db.query(Article)
        .filter(
            or_(
                Article.extracted_tickers.ilike(f"%{symbol}%"),
                Article.raw_title.ilike(f"%{symbol}%"),
                Article.raw_title.ilike(f"%{company_name.split()[0]}%"),
            ),
            Article.scraped_at >= datetime.utcnow() - timedelta(days=30),
        )
        .order_by(Article.scraped_at.desc())
        .limit(10)
        .all()
    )
    return [row.ai_title or row.raw_title for row in rows]


@router.post("/predict", response_model=PredictResponse)
def predict_asset(
    req: PredictRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user_payload),
):
    """Analyze an asset using confirmed prices, calculated metrics and stored news."""
    settings = get_settings()
    symbol = req.symbol.strip().upper()
    ticker = db.query(MarketTicker).filter(MarketTicker.symbol == symbol).first()
    if not ticker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hisse bulunamadı.")
    if ticker.is_simulated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu hissede yalnızca simülasyon verisi var. AI analizi gerçek veri gelene kadar çalıştırılmaz.",
        )
    if not ticker.price:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bu hisse için doğrulanmış fiyat verisi henüz alınamadı.",
        )

    api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    if not api_key or "xxxx" in api_key.lower():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI yapılandırılmamış. Backend OPENAI_API_KEY değerini ekleyin.",
        )

    history, history_source = fetch_history(symbol, "3m")
    if not history and ticker.history_json:
        try:
            cached = json.loads(ticker.history_json)
            history = [{"ts": ts, "price": price} for ts, price in cached]
            history_source = "last_confirmed_cache"
        except (TypeError, ValueError):
            history = []
    technical = compute_technical_context(history)
    quote_facts = extract_quote_facts(symbol, fetch_quote_summary(symbol))
    headlines = _recent_news(db, symbol, ticker.name)
    # User-supplied headlines may supplement the internal feed, but are marked as
    # untrusted context and never override calculated facts.
    supplemental = [str(item)[:300] for item in (req.news_headlines or [])[:5]]
    all_headlines = list(dict.fromkeys(headlines + supplemental))[:12]

    freshness = "unknown"
    if ticker.last_updated:
        age_minutes = max(0, int((datetime.utcnow() - ticker.last_updated).total_seconds() / 60))
        freshness = f"{age_minutes} dakika önce"
    data_quality = (
        f"Fiyat kaynağı: {ticker.source or 'bilinmiyor'}; grafik kaynağı: {history_source}; "
        f"son güncelleme: {freshness}; haber sayısı: {len(headlines)}."
    )
    question = (req.question or "Bu hisseyi kısa ve orta vadeli risk-getiri açısından değerlendir.").strip()

    system_prompt = (
        "Sen Slayz şirket içi piyasa analistisin. Yalnızca verilen doğrulanmış sayısal verileri ve haber başlıklarını kullan. "
        "Verilmeyen bilanço, fiyat hedefi, şirket haberi veya oran uydurma. Gerçek ile çıkarımı açıkça ayır. "
        "Teknik görünümü destek/direnç, dönem getirisi, oynaklık ve maksimum geri çekilme üzerinden açıkla. "
        "Haber yoksa bunu söyle. Kesin al/sat emri verme. Yanıt Türkçe ve profesyonel olsun. "
        "Sadece JSON döndür: summary, stance (pozitif|negatif|nötr), confidence (düşük|orta|yüksek), "
        "technical_view, catalysts (en fazla 4), risks (en fazla 5), reasoning."
    )
    user_payload = {
        "symbol": symbol,
        "company": ticker.name,
        "question": question,
        "current_quote": {
            "price": ticker.price,
            "currency": ticker.currency,
            "daily_change_percent": ticker.change_percent,
            "source": ticker.source,
            "last_updated": ticker.last_updated.isoformat() if ticker.last_updated else None,
        },
        "calculated_technical_metrics": technical,
        "provider_quote_facts": quote_facts,
        "recent_internal_news_headlines": all_headlines,
        "data_quality": data_quality,
    }

    try:
        import httpx
        from openai import OpenAI

        client = OpenAI(api_key=api_key, http_client=httpx.Client(timeout=60.0))
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, default=str)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=650,
        )
        data = json.loads(response.choices[0].message.content or "{}")
    except Exception as exc:  # noqa: BLE001
        logger.error("OpenAI grounded stock analysis failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI analizi alınamadı. Servis bağlantısını ve model ayarını kontrol edin.",
        ) from exc

    summary = str(data.get("summary") or "Analiz oluşturulamadı.").strip()
    stance = str(data.get("stance") or "nötr").strip().lower()
    if stance not in {"pozitif", "negatif", "nötr"}:
        stance = "nötr"
    confidence = str(data.get("confidence") or "düşük").strip().lower()
    if confidence not in {"düşük", "orta", "yüksek"}:
        confidence = "düşük"

    return PredictResponse(
        symbol=symbol,
        prediction=summary,
        summary=summary,
        stance=stance,
        sentiment=stance,
        confidence=confidence,
        technical_view=str(data.get("technical_view") or "Yeterli teknik yorum üretilemedi.").strip(),
        catalysts=_clean_list(data.get("catalysts"), 4),
        risks=_clean_list(data.get("risks"), 5),
        data_quality=data_quality,
        metrics={**technical, **{key: value for key, value in quote_facts.items() if value is not None}},
        reasoning=str(data.get("reasoning") or "").strip() or None,
        disclaimer="Bu içerik yatırım tavsiyesi değildir; şirket içi bilgi ve araştırma desteğidir.",
        generated_at=datetime.utcnow(),
    )


@router.get("/health")
def ai_health():
    settings = get_settings()
    return {
        "status": "ok",
        "openai_configured": bool(settings.openai_api_key),
        "model": settings.llm_model,
        "grounded_market_analysis": True,
    }
