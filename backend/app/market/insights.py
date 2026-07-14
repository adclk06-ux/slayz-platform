"""Market overview, thematic baskets and quantitative AI context."""
from __future__ import annotations

import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from statistics import mean, pstdev
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.market.market_data import extract_dividend_event, fetch_quote_summary
from app.models import MarketTicker

logger = logging.getLogger("slayz.market.insights")

# These are sector-sensitivity watchlists, not claims that a company will
# necessarily rise or fall in a specific conflict.
WAR_POSITIVE = {
    "ASELS": "Savunma elektroniği ve güvenlik harcamalarına duyarlılık",
    "OTKAR": "Savunma araçları ve kamu siparişlerine duyarlılık",
    "ALTNY": "Savunma ve havacılık teknolojileri teması",
    "TUPRS": "Rafineri marjları ve enerji fiyatlarına duyarlılık",
    "PETKM": "Petrokimya ve enerji fiyatlama etkisi",
    "KOZAL": "Güvenli liman altın temasına operasyonel duyarlılık",
    "KOZAA": "Altın ve madencilik temasına duyarlılık",
    "TRALT": "Altın fiyatı ve güvenli liman talebi teması",
}

WAR_NEGATIVE = {
    "THYAO": "Yakıt maliyeti, rota kapanması ve seyahat talebi riski",
    "PGSUS": "Yakıt maliyeti ve bölgesel uçuş trafiği riski",
    "TAVHL": "Yolcu trafiği ve bölgesel havalimanı operasyon riski",
    "FROTO": "Tedarik zinciri, lojistik ve dış talep riski",
    "TOASO": "Tedarik zinciri ve tüketici talebi riski",
    "ARCLK": "İthal girdi, lojistik ve tüketici güveni riski",
    "VESTL": "İthal girdi ve ihracat pazarlarında talep riski",
    "AEFES": "Bölgesel operasyon ve tüketici talebi riski",
}

DIVIDEND_CANDIDATES = [
    "AKBNK", "AKSA", "ANSGR", "BIMAS", "CIMSA", "DOAS", "ENJSA", "ENKAI",
    "EREGL", "FROTO", "GARAN", "ISCTR", "ISMEN", "KCHOL", "MGROS", "SAHOL",
    "SISE", "TCELL", "TOASO", "TSKB", "TTKOM", "TUPRS", "TURSG", "ULKER", "YKBNK",
]

_cache_lock = threading.Lock()
_dividend_cache: dict = {"expires": 0.0, "items": [], "status": "unavailable"}
_dividend_refreshing = False


def _ticker_payload(ticker: MarketTicker, reason: Optional[str] = None) -> dict:
    return {
        "id": ticker.id,
        "symbol": ticker.symbol,
        "name": ticker.name,
        "category": ticker.category,
        "price": ticker.price,
        "change": ticker.change,
        "change_percent": ticker.change_percent,
        "currency": ticker.currency,
        "source": ticker.source,
        "is_simulated": ticker.is_simulated,
        "last_updated": ticker.last_updated,
        "reason": reason,
    }


def _number(value: Optional[str]) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _theme_items(tickers_by_symbol: Dict[str, MarketTicker], definitions: Dict[str, str]) -> List[dict]:
    items = []
    for symbol, reason in definitions.items():
        ticker = tickers_by_symbol.get(symbol)
        if ticker:
            items.append(_ticker_payload(ticker, reason))
    return items


def _fetch_one_dividend(symbol: str, name: str) -> Optional[dict]:
    try:
        return extract_dividend_event(symbol, name, fetch_quote_summary(symbol))
    except Exception as exc:  # noqa: BLE001
        logger.info("Dividend lookup failed for %s: %s", symbol, exc)
        return None


def _refresh_dividend_cache(tickers_by_symbol: Dict[str, MarketTicker], max_items: int) -> None:
    global _dividend_refreshing
    results: List[dict] = []
    try:
        candidates = [
            (symbol, tickers_by_symbol[symbol].name)
            for symbol in DIVIDEND_CANDIDATES
            if symbol in tickers_by_symbol
        ]
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(_fetch_one_dividend, symbol, name) for symbol, name in candidates]
            for future in as_completed(futures):
                item = future.result()
                if item:
                    results.append(item)

        today = date.today()
        horizon = today + timedelta(days=180)
        valid: List[dict] = []
        for item in results:
            raw_date = item.get("ex_dividend_date") or item.get("payment_date")
            try:
                event_date = date.fromisoformat(raw_date) if raw_date else None
            except ValueError:
                event_date = None
            if event_date and today <= event_date <= horizon:
                valid.append(item)
        valid.sort(key=lambda item: item.get("ex_dividend_date") or item.get("payment_date") or "9999")
        valid = valid[:max_items]
        status = "live" if valid else "unavailable"
        with _cache_lock:
            _dividend_cache.update({"expires": time.time() + 1800, "items": valid, "status": status})
    finally:
        with _cache_lock:
            _dividend_refreshing = False


def upcoming_dividends(tickers_by_symbol: Dict[str, MarketTicker], max_items: int = 8) -> tuple[List[dict], str]:
    """Return cached announced dividends and refresh the provider cache in background."""
    global _dividend_refreshing
    now = time.time()
    with _cache_lock:
        items = list(_dividend_cache["items"])
        status = str(_dividend_cache["status"])
        expired = _dividend_cache["expires"] <= now
        if expired and not _dividend_refreshing:
            _dividend_refreshing = True
            thread = threading.Thread(
                target=_refresh_dividend_cache,
                args=(dict(tickers_by_symbol), max_items),
                daemon=True,
                name="slayz-dividend-refresh",
            )
            thread.start()
    return items, status


def build_market_overview(db: Session) -> dict:
    tickers = db.query(MarketTicker).all()
    by_symbol = {ticker.symbol: ticker for ticker in tickers}
    real_equities = [
        ticker for ticker in tickers
        if (
            ticker.category == "equity"
            and not ticker.is_simulated
            and ticker.price is not None
            and bool(ticker.source)
            and str(ticker.source).startswith("yahoo")
        )
    ]
    top_gainers = sorted(real_equities, key=lambda ticker: _number(ticker.change_percent), reverse=True)[:8]
    dividends, dividend_status = upcoming_dividends(by_symbol)
    return {
        "generated_at": datetime.utcnow(),
        "real_data_only": True,
        "methodology": (
            "Savaş listeleri sektör hassasiyeti izleme sepetidir; gerçekleşmiş getiri veya yatırım tavsiyesi değildir. "
            "En çok yükselenler yalnızca gerçek sağlayıcı verisi bulunan hisselerden hesaplanır."
        ),
        "war_winners": _theme_items(by_symbol, WAR_POSITIVE),
        "war_losers": _theme_items(by_symbol, WAR_NEGATIVE),
        "top_gainers": [_ticker_payload(ticker) for ticker in top_gainers],
        "upcoming_dividends": dividends,
        "dividend_status": dividend_status,
    }


def compute_technical_context(points: Iterable[dict]) -> dict:
    rows = [point for point in points if point.get("price") is not None]
    prices = [float(point["price"]) for point in rows]
    if len(prices) < 2:
        return {
            "point_count": len(prices),
            "period_return_percent": None,
            "volatility_percent": None,
            "max_drawdown_percent": None,
            "support": None,
            "resistance": None,
            "trend": "insufficient_data",
        }
    returns = [(prices[index] / prices[index - 1]) - 1 for index in range(1, len(prices)) if prices[index - 1]]
    period_return = ((prices[-1] / prices[0]) - 1) * 100 if prices[0] else 0
    volatility = pstdev(returns) * math.sqrt(max(len(returns), 1)) * 100 if len(returns) > 1 else 0
    running_peak = prices[0]
    max_drawdown = 0.0
    for price in prices:
        running_peak = max(running_peak, price)
        if running_peak:
            max_drawdown = min(max_drawdown, (price / running_peak) - 1)
    recent = prices[-min(20, len(prices)):]
    short = prices[-min(5, len(prices)):]
    long_avg = mean(recent)
    short_avg = mean(short)
    threshold = 0.002
    if short_avg > long_avg * (1 + threshold):
        trend = "up"
    elif short_avg < long_avg * (1 - threshold):
        trend = "down"
    else:
        trend = "sideways"
    return {
        "point_count": len(prices),
        "period_return_percent": round(period_return, 2),
        "volatility_percent": round(volatility, 2),
        "max_drawdown_percent": round(max_drawdown * 100, 2),
        "support": round(min(recent), 4),
        "resistance": round(max(recent), 4),
        "trend": trend,
        "latest_price": round(prices[-1], 4),
    }
