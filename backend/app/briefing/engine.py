"""
Scheduled Briefing Engine.

Triggers at 08:00 and 16:00 local time, fetches all new, unreviewed articles
ingested since the previous snapshot, and asks the LLM to generate a hyper-
condensed macro summary of maximum 80 words. The summary focuses purely on
critical data points, monetary policy changes, and sudden market shifts.
"""
import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm.analyzer import _get_client
from app.models import Article, ArticleStatus, BriefingSnapshot

logger = logging.getLogger("slayz.briefing")
settings = get_settings()

MAX_BRIEFING_WORDS = 80

_BRIEFING_SYSTEM_PROMPT = (
    "You are the lead macro analyst for an institutional research desk. "
    "Summarize the supplied financial headlines in at most 80 words. "
    "Focus only on critical data points, monetary policy changes, and sudden market shifts. "
    "Use terse, professional language. Output raw text only, no JSON."
)


def _word_count(text: str) -> int:
    return len(text.split())


def _build_headlines_payload(articles: List[Article]) -> str:
    """Compact representation of the unreviewed article batch for the LLM."""
    lines = []
    for article in articles:
        title = article.ai_title or article.raw_title or ""
        sources = [article.source_name]
        if article.duplicate_source_names:
            try:
                sources.extend(json.loads(article.duplicate_source_names))
            except json.JSONDecodeError:
                pass
        lines.append(f"- {title} ({', '.join(sources)})")
    return "\n".join(lines)


def _generate_summary(articles: List[Article]) -> str:
    """Call the LLM backend and enforce the 80-word ceiling."""
    if not articles:
        return "No new unreviewed articles since the last briefing."

    if not settings.openai_api_key:
        logger.warning("OpenAI API key missing; returning fallback briefing summary.")
        return _fallback_summary(articles)

    payload = _build_headlines_payload(articles)
    user_prompt = (
        "Write a hyper-condensed macro summary (max 80 words) of the following "
        "new, unreviewed financial headlines. Focus on critical data points, "
        "monetary policy changes, and sudden market shifts.\n\n" + payload
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _BRIEFING_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=200,
        )
        summary = response.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM briefing generation failed: %s", exc, exc_info=True)
        summary = _fallback_summary(articles)

    # Hard ceiling: truncate to the last complete word under 80 words.
    words = summary.split()
    if len(words) > MAX_BRIEFING_WORDS:
        summary = " ".join(words[:MAX_BRIEFING_WORDS]) + "."
    return summary


def _fallback_summary(articles: List[Article]) -> str:
    """Rule-based fallback when LLM is unavailable; still respects 80 words."""
    titles = [a.ai_title or a.raw_title for a in articles[:6]]
    joined = " | ".join(titles)
    fallback = f"Briefing snapshot covers {len(articles)} unreviewed items: {joined}"
    words = fallback.split()
    if len(words) > MAX_BRIEFING_WORDS:
        fallback = " ".join(words[:MAX_BRIEFING_WORDS]) + "."
    return fallback


def create_briefing_snapshot(db: Session, slot: str) -> BriefingSnapshot:
    """Create and persist a briefing snapshot for the requested time slot.

    Articles ingested since the previous snapshot (or the start of the slot)
    and still unreviewed are aggregated.
    """
    last_snapshot = (
        db.query(BriefingSnapshot)
        .order_by(BriefingSnapshot.created_at.desc())
        .first()
    )
    since = last_snapshot.created_at if last_snapshot else datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    articles = (
        db.query(Article)
        .filter(
            Article.scraped_at >= since,
            Article.status.in_([ArticleStatus.PENDING_ANALYSIS, ArticleStatus.PENDING_REVIEW]),
        )
        .order_by(Article.scraped_at.desc())
        .all()
    )

    summary = _generate_summary(articles)
    snapshot = BriefingSnapshot(
        slot=slot,
        article_ids=json.dumps([a.id for a in articles]),
        summary=summary,
        word_count=_word_count(summary),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    logger.info(
        "Briefing snapshot created at %s for slot %s: %d articles, %d words",
        snapshot.created_at,
        slot,
        len(articles),
        snapshot.word_count,
    )
    return snapshot


def run_morning_briefing(db: Session) -> BriefingSnapshot:
    """08:00 scheduled trigger."""
    return create_briefing_snapshot(db, slot="08:00")


def run_afternoon_briefing(db: Session) -> BriefingSnapshot:
    """16:00 scheduled trigger."""
    return create_briefing_snapshot(db, slot="16:00")
