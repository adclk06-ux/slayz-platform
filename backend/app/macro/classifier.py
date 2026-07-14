"""
Macro Economic Impact classifier.

Tags incoming articles with a geographic region (US, TR, JP, EZ) and a high-impact
indicator type (interest, employment, gdp) when the title/content matches
curated keyword sets. This drives the Macro/Econ dashboard filter and briefing
engine summaries.
"""
import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger("slayz.macro")

# Region keyword clouds. A headline can match multiple regions; we return the
# strongest (first) match because macro data is usually reported per-region.
_REGION_KEYWORDS = {
    "US": [
        "abd", "amerika", "united states", "us ", "us:", "(us)", "fed", "federal reserve", "powell",
        "non-farm", "nonfarm", "nfp", "fomc", "wall street", "nasdaq", "nyse",
    ],
    "TR": [
        "türkiye", "turkey", "tcmb", "merkez bankası", "merkez bankasi",
        "turkish", "türk", "istihdam", "işsizlik", "issizlik", "büyüme",
        "buyume", "faiz", "enflasyon", "bist", "borsa istanbul",
    ],
    "JP": [
        "japan", "japonya", "boj", "bank of japan", "jpy", "nihon", "japanese",
        "tokyo", "nikkei",
    ],
    "EZ": [
        "eurozone", "euro area", "euro bölgesi", "euro bolgesi", "ecb", "european central bank",
        "avro", "euro", "avropa", "europe", "eu ", "avrupa merkez bankası", "eurostoxx", "dax", "cac",
    ],
}

_INDICATOR_KEYWORDS = {
    "interest": [
        "faiz", "interest rate", "policy rate", "fomc", "tcmb", "fed", "ecb", "boj",
        "merkez bankası", "merkez bankasi", "repo", "tahvil", "bond",
    ],
    "employment": [
        "istihdam", "işsizlik", "issizlik", "employment", "unemployment",
        "non-farm", "nonfarm", "nfp", "jobless", "jobs", "iş gücü", "is gucu",
    ],
    "gdp": [
        "gdp", "büyüme", "buyume", "growth", "gsyih", "gsyh", "ekonomik büyüme",
    ],
}


def _normalize(text: str) -> str:
    """Lowercase and fold Turkish characters for keyword matching."""
    text = text.lower()
    replacements = str.maketrans({
        "ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    })
    return text.translate(replacements)


def classify_macro(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (region, indicator) tuple for the given text.

    region: US | TR | JP | EZ
    indicator: interest | employment | gdp
    """
    if not text:
        return None, None

    haystack = _normalize(text)
    region: Optional[str] = None
    indicator: Optional[str] = None

    for region_code, keywords in _REGION_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            region = region_code
            break

    for indicator_code, keywords in _INDICATOR_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            indicator = indicator_code
            break

    return region, indicator


def is_macro_relevant(text: str) -> bool:
    """Quick check: does this article look like a macro/economic data point?"""
    region, indicator = classify_macro(text)
    return region is not None and indicator is not None
