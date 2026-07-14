"""Market data endpoints: real quotes, overview lists and chart history."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.market.insights import build_market_overview
from app.market.market_data import HISTORY_RANGES, extract_quote_facts, fetch_history, fetch_quote_summary
from app.market.ticker_worker import refresh_tickers, seed_history
from app.models import MarketTicker
from app.rate_limit import limiter
from app.schemas import TickerHistoryPoint, TickerOut
from app.security import Role, require_roles

router = APIRouter(prefix="/api/market", tags=["market"])
settings = get_settings()


@router.get("/tickers", response_model=List[TickerOut])
@limiter.limit("60/minute")
def list_tickers(request: Request, category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(MarketTicker)
    if category:
        query = query.filter(MarketTicker.category == category.lower())
    return query.order_by(MarketTicker.category, MarketTicker.name).all()


@router.get("/overview")
@limiter.limit("20/minute")
def market_overview(request: Request, db: Session = Depends(get_db)):
    """Return thematic watchlists, real-data gainers and announced dividends."""
    return build_market_overview(db)


@router.get("/tickers/{symbol}", response_model=TickerOut)
@limiter.limit("60/minute")
def get_ticker(request: Request, symbol: str, db: Session = Depends(get_db)):
    ticker = db.query(MarketTicker).filter(MarketTicker.symbol == symbol.upper()).first()
    if not ticker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Varlık bulunamadı.")
    return ticker


@router.get("/tickers/{symbol}/detail")
@limiter.limit("30/minute")
def get_ticker_detail(request: Request, symbol: str, db: Session = Depends(get_db)):
    ticker = db.query(MarketTicker).filter(MarketTicker.symbol == symbol.upper()).first()
    if not ticker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Varlık bulunamadı.")
    facts = extract_quote_facts(symbol, fetch_quote_summary(symbol))
    return {
        "symbol": ticker.symbol,
        "name": ticker.name,
        "price": ticker.price,
        "change": ticker.change,
        "change_percent": ticker.change_percent,
        "currency": ticker.currency,
        "last_updated": ticker.last_updated,
        "is_simulated": ticker.is_simulated,
        "quote_status": ticker.source or "unavailable",
        **facts,
    }


@router.get("/tickers/{symbol}/history", response_model=List[TickerHistoryPoint])
@limiter.limit("60/minute")
def get_ticker_history(
    request: Request,
    symbol: str,
    period: str = Query(default="1d", pattern="^(1d|1w|1m|3m|1y|5y)$"),
    db: Session = Depends(get_db),
):
    """Return provider OHLCV data for the requested Midas-style time range."""
    symbol = symbol.upper()
    ticker = db.query(MarketTicker).filter(MarketTicker.symbol == symbol).first()
    if not ticker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Varlık bulunamadı.")

    points, _ = fetch_history(symbol, period)
    if points:
        return points

    # A last-confirmed intraday cache can still be displayed; simulated data is
    # never used as a real market chart.
    if period == "1d" and ticker.history_json and not ticker.is_simulated:
        import json

        try:
            cached = json.loads(ticker.history_json)
            return [{"ts": ts, "price": price, "close": price} for ts, price in cached]
        except (TypeError, ValueError):
            pass
    return []


@router.get("/ranges")
def supported_ranges():
    return {"ranges": list(HISTORY_RANGES.keys())}


@router.post("/refresh")
@limiter.limit("10/minute")
def trigger_refresh(request: Request, _: dict = Depends(require_roles(Role.ADMIN))):
    refreshed = refresh_tickers()
    return {"status": "ok", "count": len(refreshed), "refreshed_at": datetime.utcnow().isoformat()}


@router.post("/seed")
@limiter.limit("5/minute")
def trigger_seed(request: Request, _: dict = Depends(require_roles(Role.ADMIN))):
    seed_history()
    return {"status": "ok", "seeded_at": datetime.utcnow().isoformat()}


@router.get("/ai-insight")
@limiter.limit("30/minute")
def get_ai_insight(request: Request, db: Session = Depends(get_db)):
    """Public landing insight generated only when real market data and AI exist."""
    tickers = (
        db.query(MarketTicker)
        .filter(MarketTicker.is_simulated.is_(False), MarketTicker.price.isnot(None))
        .order_by(MarketTicker.last_updated.desc())
        .limit(5)
        .all()
    )
    if not tickers:
        return {"insight": "Canlı piyasa verisi henüz alınamadı.", "status": "unavailable"}
    if not settings.openai_api_key:
        return {"insight": "Piyasa verisi hazır; AI özeti için OpenAI yapılandırılmalı.", "status": "ai_unavailable"}
    try:
        from app.llm.assistant import chat_with_assistant

        context = "\n".join(
            f"- {ticker.symbol}: {ticker.price} {ticker.currency} ({ticker.change_percent}%)"
            for ticker in tickers
        )
        reply = chat_with_assistant(
            [{"role": "user", "content": "Aşağıdaki gerçek fiyat hareketlerinden tek cümlelik tarafsız Türkçe piyasa özeti üret."}],
            context,
        )
        return {"insight": reply, "status": "live"}
    except Exception:
        return {"insight": "AI piyasa özeti geçici olarak alınamadı.", "status": "ai_error"}
