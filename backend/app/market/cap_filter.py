"""
Market capitalization smart filter.

Cross-references extracted tickers against Yahoo Finance via yfinance to obtain
current market caps. Caches results for 6 hours to avoid hammering the upstream
API and to keep ingestion fast.
"""
import json
import logging
import os
import tempfile
import time
from typing import Dict, List, Optional

logger = logging.getLogger("slayz.market_cap")

# Mega-cap threshold in USD.
MEGA_CAP_THRESHOLD_USD = 100_000_000_000

# In-memory cache with TTL (seconds).
_CACHE_TTL = 60 * 60 * 6  # 6 hours
_cache: Dict[str, dict] = {}


def _cache_path() -> str:
    """Persistent on-disk cache inside the temp directory so restarts are cheap."""
    return os.path.join(tempfile.gettempdir(), "slayz_market_cap_cache.json")


def _load_cache() -> None:
    global _cache
    try:
        with open(_cache_path(), "r", encoding="utf-8") as f:
            raw = json.load(f)
        _cache = {k: v for k, v in raw.items() if time.time() - v.get("ts", 0) < _CACHE_TTL}
    except (FileNotFoundError, json.JSONDecodeError):
        _cache = {}


def _save_cache() -> None:
    try:
        with open(_cache_path(), "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not persist market cap cache: %s", exc)


def _yahoo_symbol(symbol: str) -> str:
    """Map a raw symbol to a Yahoo Finance ticker.

    For BIST symbols we append .IS; for US mega-caps the symbol is usually
    sufficient. Crypto or commodity symbols are ignored upstream.
    """
    if symbol.endswith(".IS"):
        return symbol
    # Heuristic: 3-5 letter symbols that are not obviously US large-caps might
    # be BIST. The curated ticker list already maps them, but we keep the rule
    # simple here and rely on yfinance returning data only when the suffix is
    # correct.
    return f"{symbol}.IS"


def fetch_market_cap(symbol: str) -> Optional[float]:
    """Return the latest market cap in USD for a single symbol, or None."""
    _load_cache()
    cached = _cache.get(symbol)
    if cached:
        return cached.get("cap")

    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed; cannot fetch market cap.")
        return None

    ticker = yf.Ticker(_yahoo_symbol(symbol))
    try:
        info = ticker.info
    except Exception as exc:  # noqa: BLE001
        logger.warning("yfinance lookup failed for %s: %s", symbol, exc)
        return None

    cap = info.get("marketCap")
    if cap and isinstance(cap, (int, float)):
        _cache[symbol] = {"cap": float(cap), "ts": time.time()}
        _save_cache()
        return float(cap)

    return None


def get_largest_market_cap(symbols: List[str]) -> Optional[float]:
    """Given a list of symbols, return the largest market cap in USD."""
    if not symbols:
        return None
    best: Optional[float] = None
    for symbol in symbols:
        cap = fetch_market_cap(symbol)
        if cap and (best is None or cap > best):
            best = cap
    return best


def is_mega_cap(cap: Optional[float]) -> bool:
    return bool(cap and cap >= MEGA_CAP_THRESHOLD_USD)
