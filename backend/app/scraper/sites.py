"""
Real-time, rate-limited scraping layer for live financial news sources.

No mock/test/placeholder data: every adapter here hits a real, live endpoint
(RSS feed or HTML listing page) for Bloomberg HT, Investing.com (TR), Investing.com
(TR Emtia), CoinDesk, and Foreks. Category is determined dynamically per-article from
its own title/content via keyword-based `categorize_text` (see app/scraper/categorize.py),
so crypto/stocks/commodities are never mixed regardless of source.

Notes on source reliability (verified live at implementation time):
- Bloomberg HT exposes a stable public RSS feed with full descriptions.
- Investing.com (TR) exposes a public RSS feed for titles/links, but its
  article detail pages return 403 (bot-protected) even with a real browser
  User-Agent -- so this adapter uses the RSS title/description directly as
  content rather than fetching the (blocked) full article body.
- CoinDesk exposes a public RSS feed dedicated to crypto/digital assets,
  giving the Kripto Para tab a direct, reliable source of live news.
- Investing.com (TR) exposes a dedicated commodities RSS feed for gold, oil,
  and broader emtia headlines, boosting the Emtia / Altın tab volume.
- Foreks' article detail pages are also bot-protected (403), so this adapter
  parses real, live headlines from the public listing page and uses the
  headline itself as content.
"""
import logging
import random
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from app.config import get_settings
from app.models import NewsCategory
from app.scraper.categorize import categorize_text
from app.scraper.detail_fetcher import fetch_article_body

logger = logging.getLogger("slayz.scraper")
settings = get_settings()


@dataclass
class ScrapedArticle:
    source_name: str
    source_url: str
    title: str
    content: str
    category: NewsCategory


class RateLimitedSession:
    """Wraps requests with proxy rotation and enforced delay between calls."""

    def __init__(self):
        self._proxies = settings.scraper_proxy_list_parsed
        self._delay = settings.scraper_request_delay_seconds
        self._last_request_ts: Optional[float] = None

    def _pick_proxy(self) -> Optional[dict]:
        if not self._proxies:
            return None
        proxy_url = random.choice(self._proxies)
        return {"http": proxy_url, "https": proxy_url}

    def get(self, url: str, timeout: int = 25) -> Optional[requests.Response]:
        if self._last_request_ts is not None:
            elapsed = time.time() - self._last_request_ts
            if elapsed < self._delay:
                time.sleep(self._delay - elapsed)

        headers = {"User-Agent": settings.scraper_user_agent}
        try:
            response = requests.get(url, headers=headers, proxies=self._pick_proxy(), timeout=timeout)
            self._last_request_ts = time.time()
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.error("Scrape request failed for %s: %s", url, exc, exc_info=True)
            return None


_session = RateLimitedSession()


class BaseSiteAdapter:
    source_name: str = "unknown"
    max_articles: int = 20

    def fetch_articles(self) -> List[ScrapedArticle]:
        raise NotImplementedError


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


class RssSiteAdapter(BaseSiteAdapter):
    """Base adapter for real, live RSS-fed sources. Each <item> is mapped
    to a ScrapedArticle; category is derived per-article from its own
    title/description via `categorize_text`."""

    rss_url: str = ""

    def _build_content(self, title: str, description: str, link: str) -> str:
        description = _strip_html(description)
        return description or title

    def fetch_articles(self) -> List[ScrapedArticle]:
        results: List[ScrapedArticle] = []
        response = _session.get(self.rss_url)
        if response is None:
            return results

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            logger.error("Failed to parse RSS from %s: %s", self.rss_url, exc, exc_info=True)
            return results

        for item in root.findall(".//item")[: self.max_articles]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = (item.findtext("description") or "").strip()
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


class BloombergHTAdapter(RssSiteAdapter):
    """Bloomberg HT's official public RSS feed (verified live, includes
    full <description> text for each item). Detail pages are also accessible,
    so we fetch the full article body from the source URL."""

    source_name = "Bloomberg HT"
    rss_url = "https://www.bloomberght.com/rss"

    def _build_content(self, title: str, description: str, link: str) -> str:
        description = _strip_html(description)
        body = fetch_article_body(link, self.source_name)
        if body and len(body.strip()) > len(description.strip()):
            return body
        return description or title


class InvestingTRAdapter(RssSiteAdapter):
    """Investing.com (TR)'s public RSS feed. Article detail pages return
    403 (bot-protected) even with a real browser User-Agent, so the RSS
    title is used directly as content (no <description> is provided by
    this feed)."""

    source_name = "Investing.com TR"
    rss_url = "https://tr.investing.com/rss/news.rss"
    max_articles = 30


class InvestingCommoditiesAdapter(RssSiteAdapter):
    """Investing.com (TR) commodities RSS feed. Provides targeted gold,
    oil, and broader commodity headlines for the Emtia / Altın tab."""

    source_name = "Investing.com TR Emtia"
    rss_url = "https://tr.investing.com/rss/commodities.rss"
    max_articles = 25


class CoinDeskAdapter(RssSiteAdapter):
    """CoinDesk's public RSS feed provides dedicated cryptocurrency and
    digital asset news, ensuring the Kripto Para tab always has live
    high-quality content."""

    source_name = "CoinDesk"
    rss_url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    max_articles = 15


class DunyaAdapter(RssSiteAdapter):
    """Dunya.com's public RSS feed provides full article descriptions for
    Turkish financial and business news, supplementing sources whose detail
    pages are bot-protected."""

    source_name = "Dunya"
    rss_url = "https://www.dunya.com/rss"
    max_articles = 25

    def _build_content(self, title: str, description: str, link: str) -> str:
        description = _strip_html(description)
        return description or title


class ForeksAdapter(BaseSiteAdapter):
    """Foreks (ForInvest) has no public RSS feed, so this parses real, live
    headlines directly from its public news listing page. Detail pages are
    bot-protected (403), so the headline itself is used as content."""

    source_name = "Foreks"
    listing_url = "https://www.foreks.com/haberler/"

    def fetch_articles(self) -> List[ScrapedArticle]:
        results: List[ScrapedArticle] = []
        response = _session.get(self.listing_url)
        if response is None:
            return results

        soup = BeautifulSoup(response.text, "html.parser")
        seen_urls = set()

        for link in soup.select('a[href*="/haber/detay/"]'):
            href = link.get("href")
            title = (link.get("title") or link.get_text(strip=True)).strip()
            if not href or not title:
                continue
            if href.startswith("/"):
                href = f"https://www.foreks.com{href}"
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


def get_all_adapters() -> List[BaseSiteAdapter]:
    return [
        BloombergHTAdapter(),
        InvestingTRAdapter(),
        InvestingCommoditiesAdapter(),
        CoinDeskAdapter(),
        DunyaAdapter(),
        ForeksAdapter(),
    ]


def run_all_scrapers() -> List[ScrapedArticle]:
    all_articles: List[ScrapedArticle] = []
    for adapter in get_all_adapters():
        try:
            articles = adapter.fetch_articles()
            logger.info("Scraped %d live articles from %s", len(articles), adapter.source_name)
            all_articles.extend(articles)
        except Exception as exc:  # noqa: BLE001 - one source failing must never break the whole run
            logger.error("Adapter %s failed: %s", adapter.source_name, exc, exc_info=True)

    if not all_articles:
        logger.warning(
            "All live sources (Bloomberg HT / Investing.com TR / Investing.com TR Emtia / "
            "CoinDesk / Dunya / Foreks) returned no articles this run."
        )

    return all_articles
