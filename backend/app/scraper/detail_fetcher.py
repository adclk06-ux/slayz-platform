"""On-demand article body fetcher.

RSS feeds often provide only summaries. This module fetches the original article
page and extracts the full body text, falling back gracefully to the RSS summary
when the source blocks automated requests.
"""
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.config import get_settings

logger = logging.getLogger("slayz.scraper")
settings = get_settings()


def _requests_get(url: str) -> Optional[str]:
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": settings.scraper_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            timeout=12,
        )
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        logger.debug("Detail fetch failed for %s: %s", url, exc)
        return None


def _playwright_get(url: str) -> Optional[str]:
    """Headless-browser fallback for bot-protected sites (Investing.com, etc.)."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        logger.debug("Playwright not available for detail fetch: %s", exc)
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
                locale="tr-TR",
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            # Try to wait for the article body if a known selector exists.
            try:
                page.wait_for_selector("article, .articlePage, .article-content, .article__content", timeout=3000)
            except Exception:
                pass
            html = page.content()
            browser.close()
            return html
    except Exception as exc:
        logger.debug("Playwright detail fetch failed for %s: %s", url, exc)
        return None


def _extract_bloomberg_ht_body(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    # Remove script/style/nav noise before extracting text.
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    article = soup.select_one("article")
    if article:
        text = article.get_text("\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        # Remove repeated/boilerplate lines and the duplicate title line.
        cleaned = []
        seen = set()
        for line in lines:
            # Skip standalone navigation/date fragments.
            if line in ("Bloomberg HT", "Haberler", "Tüm Haberler"):
                continue
            if any(b in line for b in [
                "Türkiye'nin ekonomi platformu",
                "Google listesine ekleyin",
                "Güncelleme",
                "Etiketler",
                "Paylaş",
                "Yorum Yaz",
                "Sosyal Medyada",
                "Kaynak:",
            ]):
                continue
            # Skip date lines like "08 Temmuz 2026, 07:22".
            if len(line) <= 25 and any(c in line for c in ["2026", "2025", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]):
                continue
            # Skip exact duplicate lines (e.g., repeated title).
            if line in seen:
                continue
            seen.add(line)
            cleaned.append(line)
        return "\n\n".join(cleaned)

    # Fallback selectors
    for sel in [".article-content", ".content", ".news-detail", "main"]:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 200:
            return el.get_text("\n\n", strip=True)
    return None


def _extract_investing_body(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    for sel in [
        "article",
        ".articlePage",
        ".article-content",
        ".article__content",
        ".article-text",
        "[data-test-id='article-body']",
        "#article",
    ]:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 200:
            return el.get_text("\n\n", strip=True)
    return None


def _extract_generic_body(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    # Heuristic: find the largest paragraph cluster.
    paragraphs = soup.find_all("p")
    texts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 60]
    if texts and sum(len(t) for t in texts) > 300:
        return "\n\n".join(texts)

    for sel in ["article", "main", ".content", ".post-content"]:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 200:
            return el.get_text("\n\n", strip=True)
    return None


def fetch_article_body(source_url: str, source_name: str) -> Optional[str]:
    """Fetch and extract the full article body from the original URL."""
    html = _requests_get(source_url)
    if not html and "investing.com" in source_url:
        html = _playwright_get(source_url)
    if not html:
        return None

    if "bloomberght.com" in source_url:
        return _extract_bloomberg_ht_body(html)
    if "investing.com" in source_url:
        return _extract_investing_body(html)
    return _extract_generic_body(html)


def enrich_article_body(existing_body: str, source_url: str, source_name: str) -> str:
    """Always try to fetch the full article body from the source and keep the longest/best version."""
    if not source_url:
        return existing_body

    fetched = fetch_article_body(source_url, source_name)
    if fetched and len(fetched.strip()) > 100:
        # Prefer the fetched content when it is longer or the existing body is very short.
        if len(fetched.strip()) >= len(existing_body.strip()) or len(existing_body.strip()) < 200:
            return fetched.strip()
    return existing_body
