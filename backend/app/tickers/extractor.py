"""
Ticker & company branding extraction from raw article text.

Extracts stock symbols using a curated symbol list and a lightweight regex
fallback. Returns clean badge-ready tickers and public CDN logo URLs that can
be rendered by the Next.js dashboard without leaking secrets.
"""
import json
import logging
import re
from typing import List, Optional

from app.market.ticker_worker import TICKER_SYMBOLS

logger = logging.getLogger("slayz.tickers")

# Regex that looks for common ticker patterns: $THYAO, $AAPL, or standalone
# 3-5 uppercase letters that are not ordinary words. Avoids matching common
# all-caps words like CEO, USD, IMF, etc.
_STANDALONE_SKIP = {
    "CEO", "CFO", "CTO", "USD", "EUR", "GBP", "TRY", "JPY", "CNY", "BTC", "ETH",
    "NFT", "DAO", "ETF", "IPO", "GDP", "CPI", "PPI", "Fed", "ECB", "IMF", "BIST",
    "SPX", "NASDAQ", "NYSE", "FED", "TCMB", "OPEC", "ABD", "AB", "BM", "NATO",
    "AI", "IT", "API", "SaaS", "GPU", "CPU", "RAM", "SSD", "HTTP", "HTTPS",
}


class TickerResult:
    """Container for a discovered ticker and its public logo asset."""

    def __init__(self, symbol: str, name: str, logo_url: str):
        self.symbol = symbol
        self.name = name
        self.logo_url = logo_url

    def to_dict(self) -> dict:
        return {"symbol": self.symbol, "name": self.name, "logo_url": self.logo_url}


# Build a fast lookup from the curated BIST/equity list already maintained by
# the market ticker worker. This keeps ticker metadata (name, currency) in one
# place and avoids duplicating symbol lists.
_KNOWN_SYMBOLS: dict[str, dict] = {}
for ticker in TICKER_SYMBOLS:
    sym = ticker.get("symbol", "")
    if sym:
        _KNOWN_SYMBOLS[sym] = ticker


def _tradingview_logo_url(symbol: str, region: str = "") -> str:
    """Return a TradingView CDN-style broker logo URL for a given symbol.

    TradingView's broker logo endpoint is public and fast; we fall back to
    a Clearbit-style domain logo for non-IS symbols when possible.
    """
    if region == "TR" or symbol.endswith(".IS"):
        return f"https://tradingview.com/x/{symbol}.IS/"
    return f"https://tradingview.com/x/{symbol}/"


def _clearbit_domain_logo(domain: str) -> str:
    """Public Clearbit logo API for company website domains."""
    return f"https://logo.clearbit.com/{domain}"


def _normalize_symbol(raw: str) -> str:
    """Strip $ prefix and whitespace; uppercase the symbol."""
    return raw.strip().lstrip("$").upper()


def extract_tickers(text: str) -> List[str]:
    """Return a de-duplicated list of ticker symbols found in the text.

    Strategy:
    1. Direct mentions like $THYAO or $AAPL.
    2. Standalone uppercase tokens that exist in the curated symbol universe.
    3. Regex fallback for 3-5 letter uppercase tokens, filtered against common
       non-ticker words.
    """
    if not text:
        return []

    candidates: set[str] = set()
    haystack = text.upper()

    # 1) $-prefixed symbols.
    for match in re.finditer(r"\$([A-Z]{2,6})(?:\.IS)?\b", text):
        candidates.add(_normalize_symbol(match.group(1)))

    # 2) Known symbols from the BIST/equity list.
    for symbol in _KNOWN_SYMBOLS:
        # Word boundaries can fail for .IS suffixes, so we use a permissive
        # regex that matches the symbol optionally followed by .IS.
        pattern = rf"\b{re.escape(symbol)}(?:\.IS)?\b"
        if re.search(pattern, haystack):
            candidates.add(symbol)

    # 3) Standalone 3-5 letter uppercase tokens (fallback, heavily filtered).
    for token in re.findall(r"\b[A-Z]{3,5}\b", haystack):
        if token in _STANDALONE_SKIP:
            continue
        if token in _KNOWN_SYMBOLS:
            candidates.add(token)

    return sorted(candidates)


def enrich_tickers(symbols: List[str], region: Optional[str] = None) -> List[TickerResult]:
    """Map extracted symbols to display objects with names and logo URLs."""
    results: List[TickerResult] = []
    for symbol in symbols:
        meta = _KNOWN_SYMBOLS.get(symbol, {})
        name = meta.get("name") or symbol
        logo = _tradingview_logo_url(symbol, region or "")
        results.append(TickerResult(symbol, name, logo))
    return results


def serialize_tickers(tickers: List[str]) -> Optional[str]:
    """Persist a list of tickers as JSON in the article record."""
    if not tickers:
        return None
    return json.dumps(tickers)


def parse_tickers(serialized: Optional[str]) -> List[str]:
    if not serialized:
        return []
    try:
        return json.loads(serialized)
    except json.JSONDecodeError:
        logger.warning("Malformed ticker JSON: %s", serialized)
        return []
