"""
Article endpoints: listing, retrieval, curation (approve/reject),
institutional filters, briefing snapshots, and manual pipeline trigger.
Protected with RBAC (ANALYST/ADMIN can review).
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.email.mailer import send_shared_article
from app.llm.analyzer import analyze_article
from app.models import Article, ArticleStatus, AuditLog, BriefingSnapshot, MarketTicker, NewsCategory
from app.pipeline import run_ingestion_pipeline
from app.rate_limit import limiter
from app.schemas import (
    ArticleOut,
    ArticleReviewAction,
    BriefingSnapshotOut,
    ScrapeTriggerResponse,
    ShareArticleRequest,
)
from app.scraper.detail_fetcher import enrich_article_body
from app.security import (
    Role,
    get_current_user_payload,
    optional_current_user_payload,
    require_roles,
)

logger = logging.getLogger("slayz.articles")
router = APIRouter(prefix="/api/articles", tags=["articles"])
_feed_refresh_lock = threading.Lock()
_feed_refresh_running = False


def _refresh_feed_background() -> None:
    global _feed_refresh_running
    try:
        from app.pipeline import run_ingestion_pipeline_standalone
        result = run_ingestion_pipeline_standalone()
        logger.info("On-demand feed bootstrap complete: %s", result)
    except Exception as exc:  # noqa: BLE001
        logger.error("On-demand feed bootstrap failed: %s", exc, exc_info=True)
    finally:
        with _feed_refresh_lock:
            _feed_refresh_running = False



@router.get("", response_model=List[ArticleOut])
def list_articles(
    category: Optional[NewsCategory] = None,
    status_filter: Optional[ArticleStatus] = None,
    mega_cap_only: Optional[bool] = None,
    macro_region: Optional[str] = Query(None, max_length=8),
    macro_indicator: Optional[str] = Query(None, max_length=32),
    primary_only: bool = False,
    db: Session = Depends(get_db),
    _: Optional[dict] = Depends(optional_current_user_payload),
):
    """List articles with institutional filters.

    - mega_cap_only: restrict to companies with market cap > $100B.
    - macro_region: US, TR, JP, EZ.
    - macro_indicator: interest, employment, gdp.
    - primary_only: collapse duplicate groups into one canonical card.
    """
    query = db.query(Article)
    if category:
        query = query.filter(Article.category == category)
    if status_filter:
        query = query.filter(Article.status == status_filter)
    if mega_cap_only is True:
        query = query.filter(Article.is_mega_cap.is_(True))
    if macro_region:
        query = query.filter(Article.macro_region == macro_region.upper())
    if macro_indicator:
        query = query.filter(Article.macro_indicator == macro_indicator.lower())
    if primary_only:
        query = query.filter(Article.is_primary_duplicate.is_(True))

    return query.order_by(Article.scraped_at.desc()).limit(200).all()


@router.get("/by-ticker/{symbol}", response_model=List[ArticleOut])
def list_articles_by_ticker(
    symbol: str,
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user_payload),
):
    """Return recent articles matching the given symbol.

    Matching strategy (broad-to-narrow, OR-combined):
    1. Extracted ticker list contains the symbol (pipeline enrichment).
    2. Title (raw or AI) contains the symbol as a substring (case-insensitive).
    3. Title contains the company/asset name keyword resolved from market_tickers
       (e.g. AKSA -> "Aksa"), so brand-new articles surface before enrichment runs.
    """
    q = symbol.upper().strip()
    if not q:
        return []

    # Resolve human-readable keywords from the market ticker registry.
    keywords = {q}
    ticker_row = db.query(MarketTicker).filter(MarketTicker.symbol == q).first()
    if ticker_row and ticker_row.name:
        # First meaningful word of the company name, e.g. "Aksa Akrilik" -> "Aksa".
        first_word = ticker_row.name.split()[0].strip()
        if len(first_word) >= 3:
            keywords.add(first_word)

    conditions = [
        Article.extracted_tickers.isnot(None) & Article.extracted_tickers.contains(q),
    ]
    for kw in keywords:
        pattern = f"%{kw}%"
        conditions.append(Article.raw_title.ilike(pattern))
        conditions.append(Article.ai_title.ilike(pattern))

    matches = (
        db.query(Article)
        .filter(or_(*conditions))
        .order_by(Article.scraped_at.desc())
        .limit(limit)
        .all()
    )
    if matches:
        return matches

    # Fallback: no direct mention yet -> surface the freshest sector news for
    # the asset's category so the feed under the chart is never empty.
    category_map = {
        "equity": NewsCategory.STOCKS,
        "index": NewsCategory.STOCKS,
        "crypto": NewsCategory.CRYPTO,
        "commodity": NewsCategory.COMMODITIES,
        "forex": NewsCategory.GENERAL,
    }
    fallback_category = (
        category_map.get(ticker_row.category) if ticker_row else NewsCategory.GENERAL
    )
    query = db.query(Article)
    if fallback_category:
        query = query.filter(Article.category == fallback_category)
    return query.order_by(Article.scraped_at.desc()).limit(min(limit, 15)).all()


@router.post("/ensure-feed")
def ensure_feed(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user_payload),
):
    """Queue a non-blocking source scan when the feed is empty or stale.

    This endpoint is safe for normal users to call during app startup. It does not
    block the page while RSS/HTML sources are fetched and it coalesces concurrent
    browser requests into one background run.
    """
    global _feed_refresh_running
    latest = db.query(Article).order_by(Article.scraped_at.desc()).first()
    stale_before = datetime.utcnow() - timedelta(minutes=20)
    needs_refresh = latest is None or latest.scraped_at < stale_before

    scheduled = False
    if needs_refresh:
        with _feed_refresh_lock:
            if not _feed_refresh_running:
                _feed_refresh_running = True
                scheduled = True
                background_tasks.add_task(_refresh_feed_background)

    return {
        "scheduled": scheduled,
        "refresh_running": _feed_refresh_running,
        "has_articles": latest is not None,
        "latest_article_at": latest.scraped_at if latest else None,
    }


@router.get("/feed-status")
def feed_status(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user_payload),
):
    """Report whether the persisted feed contains live or synthetic source rows."""
    total = db.query(Article).count()
    simulated = db.query(Article).filter(Article.source_url.contains("mock-pipe.slayz.local")).count()
    latest = db.query(Article).order_by(Article.scraped_at.desc()).first()
    return {
        "total_articles": total,
        "live_articles": max(0, total - simulated),
        "simulated_articles": simulated,
        "latest_article_at": latest.scraped_at if latest else None,
        "latest_source": latest.source_name if latest else None,
        "is_live_only": simulated == 0,
    }


@router.get("/briefings", response_model=List[BriefingSnapshotOut])
def list_briefings(
    limit: int = 10,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user_payload),
):
    return (
        db.query(BriefingSnapshot)
        .order_by(BriefingSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/briefings/latest", response_model=BriefingSnapshotOut)
def get_latest_briefing(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user_payload),
):
    snapshot = db.query(BriefingSnapshot).order_by(BriefingSnapshot.created_at.desc()).first()
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Henüz bir brifing oluşturulmadı.")
    return snapshot


@router.get("/{article_id}", response_model=ArticleOut)
def get_article(
    article_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user_payload),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Haber bulunamadı.")
    # On-demand enrichment: fetch full body from the original source so the user can read it end-to-end.
    enriched = enrich_article_body(
        article.raw_content, article.source_url, article.source_name
    )
    if enriched and enriched != article.raw_content:
        article.raw_content = enriched
        db.add(article)
        db.commit()
        db.refresh(article)
    return article


@router.post("/{article_id}/review", response_model=ArticleOut)
def review_article(
    article_id: str,
    action: ArticleReviewAction,
    db: Session = Depends(get_db),
    payload: dict = Depends(require_roles(Role.ANALYST, Role.ADMIN)),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Haber bulunamadı.")

    article.status = ArticleStatus.APPROVED if action.approve else ArticleStatus.REJECTED
    article.reviewed_by = payload.get("sub")
    article.reviewed_at = datetime.utcnow()
    db.add(
        AuditLog(
            actor_id=payload.get("sub"),
            action="article_review",
            detail=f"article={article.id} approve={action.approve}",
        )
    )
    db.commit()
    db.refresh(article)
    logger.info("Article %s reviewed by %s: approve=%s", article.id, payload.get("sub"), action.approve)
    return article


@router.post("/{article_id}/analyze", response_model=ArticleOut)
@limiter.limit("30/minute")
def analyze_existing_article(
    request: Request,
    article_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """Runs the LLM analysis pipeline on demand for a single existing article."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Haber bulunamadı.")

    try:
        result = analyze_article(article.source_name, article.raw_title, article.raw_content)
    except Exception as exc:  # noqa: BLE001
        logger.error("On-demand analysis failed for article %s: %s", article.id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI analizi şu anda gerçekleştirilemiyor. Lütfen daha sonra tekrar deneyin.",
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI bağlantısı yapılandırılmamış. OPENAI_API_KEY değerini ekleyin.",
        )

    article.ai_title = result.title
    article.ai_summary = result.summary
    article.category = result.category
    article.sentiment = result.sentiment
    article.status = ArticleStatus.PENDING_REVIEW
    article.analyzed_at = datetime.utcnow()
    db.add(
        AuditLog(
            actor_id=payload.get("sub"),
            action="article_analyze",
            detail=f"article={article.id} category={result.category.value} sentiment={result.sentiment}",
        )
    )
    db.commit()
    db.refresh(article)
    logger.info("Article %s analyzed on demand by %s", article.id, payload.get("sub"))
    return article


@router.post("/{article_id}/share")
@limiter.limit("10/minute")
def share_article(
    request: Request,
    article_id: str,
    payload: ShareArticleRequest,
    db: Session = Depends(get_db),
    user_payload: dict = Depends(get_current_user_payload),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Haber bulunamadı.")

    sent = send_shared_article(article, payload.email, payload.note)
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="E-posta gönderilemedi. SMTP ayarlarını kontrol edin.",
        )

    db.add(
        AuditLog(
            actor_id=user_payload.get("sub"),
            action="article_share",
            detail=f"article={article.id} to={payload.email}",
        )
    )
    db.commit()
    logger.info("Article %s shared by %s to %s", article.id, user_payload.get("sub"), payload.email)
    return {"detail": "Haber e-posta ile gönderildi."}


@router.post("/pipeline/run", response_model=ScrapeTriggerResponse)
def trigger_pipeline(
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles(Role.ADMIN)),
):
    result = run_ingestion_pipeline(db)
    return ScrapeTriggerResponse(**result)


