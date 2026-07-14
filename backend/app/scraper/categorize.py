"""
Keyword-based smart categorization for scraped news.

Ensures articles are never mixed across categories: each article's title and
body are checked against curated Turkish keyword sets so the correct category
(and therefore the correct dashboard visual - BTC / trendline / gold) is
applied deterministically.
"""
from app.models import NewsCategory

_CRYPTO_KEYWORDS = [
    "bitcoin", "kripto", "ethereum", "btc", "eth", "altcoin", "blockchain",
    "binance", "coin", "kripto para", "coindesk", "coinbase", "kraken", "okx",
    "bybit", "ripple", "xrp", "solana", "sol", "cardano", "ada", "avalanche",
    "avax", "dogecoin", "doge", "shiba", "web3", "nft", "defi", "stablecoin",
    "kripto para birimi", "dijital para", "madencilik", "mining", "hard fork",
    "etf", "satoshi", "wallet", "cüzdan",
]

_COMMODITY_KEYWORDS = [
    "altın", "altin", "ons", "emtia", "gümüş", "gumus", "petrol", "brent",
    "doğalgaz", "dogalgaz", "bakır", "bakir", "gram altın", "çeyrek altın",
    "yarım altın", "tam altın", "cumhuriyet altını", "ham petrol", "wti",
    "natural gas", "paladyum", "platin", "buğday", "bugday", "mısır", "misir",
    "soya", "demir", "çelik", "celik", "alüminyum", "aluminyum", "çinko",
    "zinck", "kurşun", "kursun", "nikel", "kahve", "kakao", "şeker", "seker",
]

_STOCKS_KEYWORDS = [
    "borsa", "hisse", "bist100", "bist 100", "bist", "fed", "endeks",
    "tahvil", "faiz", "dolar/tl", "şirket karı", "temettü",
]

_TURKISH_CHAR_MAP = str.maketrans({
    "ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
})


def _normalize(text: str) -> str:
    return text.lower().translate(_TURKISH_CHAR_MAP)


def categorize_text(title: str, content: str = "") -> NewsCategory:
    """Deterministically categorizes a news item from its title/content.

    Priority: crypto > commodities > stocks > general. This ordering avoids
    cross-category mixing (e.g. an article mentioning both "Fed" and "altın"
    is treated as a commodities story since gold-price movements driven by
    Fed policy belong on the Emtia/Altın board).
    """
    haystack = _normalize(f"{title} {content}")

    if any(_normalize(kw) in haystack for kw in _CRYPTO_KEYWORDS):
        return NewsCategory.CRYPTO
    if any(_normalize(kw) in haystack for kw in _COMMODITY_KEYWORDS):
        return NewsCategory.COMMODITIES
    if any(_normalize(kw) in haystack for kw in _STOCKS_KEYWORDS):
        return NewsCategory.STOCKS
    return NewsCategory.GENERAL
