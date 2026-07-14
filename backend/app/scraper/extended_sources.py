"""
Extended multi-source ingestion pipeline.

Adds institutional-grade streams to the core scraper set:
- Turkish official / financial media (KAP, Ekonomi Gazetesi, Borsagundem, etc.)
- Global US sources (Bloomberg, Investing US, SeekingAlpha, Reuters, MarketWatch,
  TradingEconomics, TradingView)
- Twitter / X alpha-style streams (Deitaone, KobeissiLetter)
- Corporate actions calendar (IPOs, buybacks, earnings calls)

Only real public source adapters are registered. Synthetic headline generators are not part of the production pipeline.
"""
import logging
from dataclasses import dataclass
from typing import List

import requests
from bs4 import BeautifulSoup

from app.models import NewsCategory
from app.config import get_settings
from app.scraper.categorize import categorize_text
from app.scraper.sites import BaseSiteAdapter, RateLimitedSession, _session, _strip_html

logger = logging.getLogger("slayz.scraper.extended")
settings = get_settings()


@dataclass
class ScrapedArticle:
    source_name: str
    source_url: str
    title: str
    content: str
    category: NewsCategory


class RssSiteAdapter(BaseSiteAdapter):
    """Lightweight RSS adapter for sources that expose public feeds."""

    source_name: str = "unknown"
    rss_url: str = ""
    max_articles: int = 20

    def _build_content(self, title: str, description: str, link: str) -> str:
        return _strip_html(description) or title

    def fetch_articles(self) -> List[ScrapedArticle]:
        results: List[ScrapedArticle] = []
        try:
            response = _session.get(self.rss_url)
        except requests.RequestException as exc:
            logger.warning("Extended RSS request failed for %s: %s", self.source_name, exc)
            return results

        if response is None:
            return results

        try:
            import feedparser
        except ImportError:
            logger.error("feedparser not installed; cannot parse %s", self.source_name)
            return results

        feed = feedparser.parse(response.content)
        for entry in feed.entries[: self.max_articles]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            description = entry.get("summary", entry.get("description", "")).strip()
            if not title or not link:
                continue
            content = self._build_content(title, description, link)
            results.append(
                ScrapedArticle(
                    source_name=self.source_name,
                    source_url=link,
                    title=title,
                    content=content,
                    category=categorize_text(title, content),
                )
            )
        return results


# ---------------------------------------------------------------------------
# Real / public RSS and HTML adapters
# ---------------------------------------------------------------------------

class KAPAdapter(RssSiteAdapter):
    """Kamuyu Aydınlatma Platformu (KAP) official breaking disclosure RSS."""

    source_name = "KAP"
    rss_url = "https://www.kap.org.tr/tr/rss/sonDakika"
    max_articles = 25


class EkonomiGazetesiAdapter(RssSiteAdapter):
    """Ekonomi Gazetesi public RSS feed for Turkish business/finance news."""

    source_name = "Ekonomi Gazetesi"
    rss_url = "https://www.ekonomigazetesi.com/rss"
    max_articles = 20


class BorsagundemAdapter(BaseSiteAdapter):
    """Borsagundem HTML listing page scraper for Turkish market headlines.

    Detail pages are bot-protected, so we use the listing title as content.
    """

    source_name = "Borsagundem"
    listing_url = "https://www.borsagundem.com/haberler"
    max_articles = 20

    def fetch_articles(self) -> List[ScrapedArticle]:
        results: List[ScrapedArticle] = []
        try:
            response = _session.get(self.listing_url)
        except requests.RequestException as exc:
            logger.warning("Borsagundem request failed: %s", exc)
            return results

        if response is None:
            return results

        soup = BeautifulSoup(response.text, "html.parser")
        seen_urls = set()

        for item in soup.select("a[href*='/haber/']"):
            href = item.get("href")
            title = item.get_text(strip=True)
            if not href or not title:
                continue
            if href.startswith("/"):
                href = f"https://www.borsagundem.com{href}"
            if href in seen_urls:
                continue
            seen_urls.add(href)
            results.append(
                ScrapedArticle(
                    source_name=self.source_name,
                    source_url=href,
                    title=title,
                    content=title,
                    category=categorize_text(title, ""),
                )
            )
            if len(results) >= self.max_articles:
                break

        return results


class TradingViewEconomicsAdapter(RssSiteAdapter):
    """TradingView economic calendar RSS proxy for macro events.

    This adapter uses a public TradingView RSS endpoint and returns no data when the source is unavailable.
    """

    source_name = "TradingView"
    rss_url = "https://www.tradingview.com/news/feed/?category=economy"
    max_articles = 15

    def fetch_articles(self) -> List[ScrapedArticle]:
        results = super().fetch_articles()
        if results:
            return results
        return []


def get_extended_adapters() -> List[BaseSiteAdapter]:
    """Real public adapters merged into the main ingestion run."""
    return [
        KAPAdapter(),
        EkonomiGazetesiAdapter(),
        BorsagundemAdapter(),
        TradingViewEconomicsAdapter(),
    ]
