"""Server-side market data helpers.

Yahoo Finance is used as the default no-key provider. Responses are never
silently replaced with invented market facts. Callers receive an empty result
and a source-status value when the provider is unavailable.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.config import get_settings
from app.market.ticker_worker import _yahoo_symbol

logger = logging.getLogger("slayz.market.data")
settings = get_settings()

HISTORY_RANGES: Dict[str, Tuple[str, str]] = {
    "1d": ("1d", "5m"),
    "1w": ("5d", "30m"),
    "1m": ("1mo", "1d"),
    "3m": ("3mo", "1d"),
    "1y": ("1y", "1d"),
    "5y": ("5y", "1wk"),
}


def _request_json(url: str, *, params: Optional[dict] = None, timeout: int = 15) -> Optional[dict]:
    try:
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": settings.scraper_user_agent},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # noqa: BLE001
        logger.info("Market provider request failed: %s", exc)
        return None


def fetch_history(symbol: str, period: str = "1d") -> Tuple[List[dict], str]:
    """Return OHLCV history for a supported period and the provider name."""
    normalized = period.lower()
    if normalized not in HISTORY_RANGES:
        normalized = "1d"
    range_value, interval = HISTORY_RANGES[normalized]
    yahoo_symbol = _yahoo_symbol(symbol.upper())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
    payload = _request_json(url, params={"range": range_value, "interval": interval, "events": "div,splits"})
    result = ((payload or {}).get("chart", {}).get("result") or [None])[0]
    if not result:
        return [], "unavailable"

    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    points: List[dict] = []
    gold_multiplier = 10.0 if symbol.upper() == "XAUUSD" else 1.0
    for index, ts in enumerate(timestamps):
        close = closes[index] if index < len(closes) else None
        if close is None or ts is None:
            continue
        open_value = opens[index] if index < len(opens) else close
        high_value = highs[index] if index < len(highs) else close
        low_value = lows[index] if index < len(lows) else close
        volume = volumes[index] if index < len(volumes) else None
        points.append(
            {
                "ts": float(ts),
                "price": round(float(close) * gold_multiplier, 4),
                "open": round(float(open_value if open_value is not None else close) * gold_multiplier, 4),
                "high": round(float(high_value if high_value is not None else close) * gold_multiplier, 4),
                "low": round(float(low_value if low_value is not None else close) * gold_multiplier, 4),
                "close": round(float(close) * gold_multiplier, 4),
                "volume": float(volume) if volume is not None else None,
            }
        )
    return points, "yahoo" if points else "unavailable"


def fetch_quote_summary(symbol: str) -> Dict[str, Any]:
    """Fetch non-trading quote statistics used by the detail and AI panels."""
    yahoo_symbol = _yahoo_symbol(symbol.upper())
    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{yahoo_symbol}"
    payload = _request_json(
        url,
        params={"modules": "price,summaryDetail,defaultKeyStatistics,calendarEvents"},
        timeout=7,
    )
    result = (((payload or {}).get("quoteSummary") or {}).get("result") or [None])[0]
    return result or {}


def _raw(module: dict, key: str) -> Any:
    value = module.get(key)
    if isinstance(value, dict):
        return value.get("raw", value.get("fmt"))
    return value


def _iso_date(raw_value: Any) -> Optional[str]:
    if raw_value is None:
        return None
    try:
        if isinstance(raw_value, (int, float)):
            return datetime.fromtimestamp(raw_value, tz=timezone.utc).date().isoformat()
        return str(raw_value)[:10]
    except Exception:  # noqa: BLE001
        return None


def extract_quote_facts(symbol: str, summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    summary = summary if summary is not None else fetch_quote_summary(symbol)
    price = summary.get("price") or {}
    detail = summary.get("summaryDetail") or {}
    stats = summary.get("defaultKeyStatistics") or {}
    return {
        "market_cap": _raw(price, "marketCap") or _raw(detail, "marketCap"),
        "previous_close": _raw(detail, "previousClose"),
        "open": _raw(detail, "open"),
        "day_high": _raw(detail, "dayHigh"),
        "day_low": _raw(detail, "dayLow"),
        "fifty_two_week_high": _raw(detail, "fiftyTwoWeekHigh"),
        "fifty_two_week_low": _raw(detail, "fiftyTwoWeekLow"),
        "volume": _raw(detail, "volume"),
        "average_volume": _raw(detail, "averageVolume"),
        "trailing_pe": _raw(detail, "trailingPE"),
        "price_to_book": _raw(stats, "priceToBook"),
        "dividend_yield": _raw(detail, "dividendYield"),
        "currency": _raw(price, "currency"),
        "exchange": _raw(price, "exchangeName"),
        "source": "yahoo" if summary else "unavailable",
    }


def extract_dividend_event(symbol: str, name: str, summary: Optional[Dict[str, Any]] = None) -> Optional[dict]:
    """Extract the next announced dividend event; return None if not announced."""
    summary = summary if summary is not None else fetch_quote_summary(symbol)
    if not summary:
        return None
    calendar = summary.get("calendarEvents") or {}
    detail = summary.get("summaryDetail") or {}
    dividend_date = _raw(calendar, "dividendDate")
    ex_dividend_date = _raw(calendar, "exDividendDate") or _raw(detail, "exDividendDate")
    amount = _raw(calendar, "dividendRate") or _raw(detail, "dividendRate")
    if dividend_date is None and ex_dividend_date is None:
        return None
    return {
        "symbol": symbol,
        "name": name,
        "ex_dividend_date": _iso_date(ex_dividend_date),
        "payment_date": _iso_date(dividend_date),
        "amount": float(amount) if isinstance(amount, (int, float)) else None,
        "currency": _raw(summary.get("price") or {}, "currency") or "TRY",
        "source": "yahoo",
    }
