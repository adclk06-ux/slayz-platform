"""
Orchestrates the full pipeline: scrape -> enrich -> dedup -> LLM analysis -> persist -> email notify.
"""
import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.deduplication.engine import aggregate_secondary_sources, assign_duplicate_group
from app.email.mailer import send_article_for_review
from app.llm.analyzer import analyze_article
from app.macro.classifier import classify_macro
from app.market.cap_filter import get_largest_market_cap, is_mega_cap
from app.models import Article, ArticleStatus
from app.scraper.extended_sources import get_extended_adapters
from app.scraper.sites import run_all_scrapers
from app.tickers.extractor import enrich_tickers, extract_tickers, serialize_tickers
from app.websocket.manager import manager as websocket_manager

logger = logging.getLogger("slayz.pipeline")


def _fetch_recent_articles(db: Session) -> list[Article]:
    """Load the last 200 persisted articles for deduplication comparison."""
    return (
        db.query(Article)
        .order_by(Article.scraped_at.desc())
        .limit(200)
        .all()
    )


def _enrich_article(article: Article) -> None:
    """Apply ticker extraction, macro tagging, market-cap lookup, and dedup grouping.

    Mutates the article in place. Must be called before the article is committed
    for the first time so the LLM prompt and downstream filters benefit from the
    metadata.
    """
    # 1. Tickers and branding metadata.
    full_text = f"{article.raw_title}\n{article.raw_content}"
    tickers = extract_tickers(full_text)
    article.extracted_tickers = serialize_tickers(tickers)

    # 2. Macro region / indicator classification.
    region, indicator = classify_macro(full_text)
    article.macro_region = region
    article.macro_indicator = indicator

    # 3. Market cap filter (best-effort; cached upstream lookups).
    if tickers:
        try:
            largest_cap = get_largest_market_cap(tickers)
            if largest_cap:
                article.market_cap_usd = str(int(largest_cap))
                article.is_mega_cap = is_mega_cap(largest_cap)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Market cap lookup failed for %s: %s", article.raw_title, exc)


def run_ingestion_pipeline(db: Session) -> dict:
    """Run the full ingestion and analysis pipeline."""
    # Core live scrapers plus extended institutional streams.
    scraped_articles = run_all_scrapers()
    for adapter in get_extended_adapters():
        try:
            adapter_articles = adapter.fetch_articles()
            scraped_articles.extend(adapter_articles)
            logger.info("Extended adapter %s scraped %d articles", adapter.source_name, len(adapter_articles))
        except Exception as exc:  # noqa: BLE001
            logger.error("Extended adapter %s failed: %s", adapter.source_name, exc, exc_info=True)

    scraped_count = 0
    analyzed_count = 0
    emailed_count = 0
    persisted: list[Article] = []
    recent_articles = _fetch_recent_articles(db)

    for scraped in scraped_articles:
        existing = db.query(Article).filter(Article.source_url == scraped.source_url).first()
        if existing:
            continue

        article = Article(
            source_name=scraped.source_name,
            source_url=scraped.source_url,
            category=scraped.category,
            raw_title=scraped.title,
            raw_content=scraped.content,
            status=ArticleStatus.PENDING_ANALYSIS,
        )
        _enrich_article(article)
        assign_duplicate_group(article, recent_articles)
        db.add(article)
        db.commit()
        db.refresh(article)
        scraped_count += 1
        persisted.append(article)
        # Keep the in-memory list fresh for subsequent duplicate checks.
        recent_articles.insert(0, article)

        result = analyze_article(scraped.source_name, scraped.title, scraped.content)
        if result is None:
            # Demo/local mode: LLM is intentionally disabled. Keep the raw article
            # available for review without spamming the error log.
            article.status = ArticleStatus.PENDING_REVIEW
            db.commit()
            continue

        article.ai_title = result.title
        article.ai_summary = result.summary
        article.category = result.category
        article.sentiment = result.sentiment
        article.status = ArticleStatus.PENDING_REVIEW
        article.analyzed_at = datetime.utcnow()
        db.commit()
        analyzed_count += 1

        if send_article_for_review(article):
            article.email_sent = True
            db.commit()
            emailed_count += 1

    # After the batch is persisted, rebuild secondary source lists for each group.
    if persisted:
        aggregate_secondary_sources(db, persisted)
        db.commit()

    # Push a real-time notification to every connected desk client.
    if scraped_count > 0:
        try:
            websocket_manager.broadcast_sync({
                "type": "new_articles",
                "count": scraped_count,
            })
            logger.info("Broadcasted new_articles event with count=%d", scraped_count)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to broadcast new_articles event: %s", exc)

    return {"scraped": scraped_count, "analyzed": analyzed_count, "emailed": emailed_count}


def run_ingestion_pipeline_standalone() -> dict:
    """Entry point for scheduled jobs that need their own DB session."""
    db = SessionLocal()
    try:
        return run_ingestion_pipeline(db)
    finally:
        db.close()
