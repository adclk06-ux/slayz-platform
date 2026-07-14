"""
Semantic deduplication & anti-spam filter.

Compares incoming articles against recent articles using TF-IDF + cosine
similarity. When similarity exceeds a threshold, the articles are merged into a
single duplicate group. The primary card keeps the canonical headline; secondary
sources are listed as icons underneath to keep the dashboard clean.
"""
import hashlib
import json
import logging
from typing import List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import Article

logger = logging.getLogger("slayz.dedup")

# Similarity threshold for near-duplicate detection. 0.85 catches rewritten
# headlines and minor paraphrases while avoiding false positives.
SIMILARITY_THRESHOLD = 0.85


def _article_signature(article: Article) -> str:
    """Text signature used for TF-IDF comparison."""
    title = article.raw_title or ""
    content = (article.raw_content or "")[:400]
    return f"{title}\n{content}"


def _generate_group_id(articles: List[Article]) -> str:
    """Deterministic group id from the sorted source URLs of the cluster."""
    urls = sorted(a.source_url for a in articles if a.source_url)
    return hashlib.sha256("|".join(urls).encode("utf-8")).hexdigest()[:16]


def find_duplicate_group(
    incoming: Article,
    recent_articles: List[Article],
    vectorizer: Optional[TfidfVectorizer] = None,
) -> Optional[str]:
    """Return the duplicate_group_id of the most similar recent article, or None."""
    if not recent_articles:
        return None

    candidates = [a for a in recent_articles if a.duplicate_group_id and a.is_primary_duplicate]
    if not candidates:
        return None

    texts = [_article_signature(incoming)] + [_article_signature(a) for a in candidates]
    try:
        vect = vectorizer or TfidfVectorizer(stop_words="english", max_features=5000, ngram_range=(1, 2))
        matrix = vect.fit_transform(texts)
    except ValueError as exc:
        logger.warning("TF-IDF vectorization failed: %s", exc)
        return None

    similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    best_idx = int(similarities.argmax())
    best_score = float(similarities[best_idx])

    logger.debug(
        "Deduplication check for '%s...' best score %.3f against %s",
        incoming.raw_title[:40],
        best_score,
        candidates[best_idx].source_name,
    )

    if best_score >= SIMILARITY_THRESHOLD:
        return candidates[best_idx].duplicate_group_id

    return None


def assign_duplicate_group(
    incoming: Article,
    recent_articles: List[Article],
) -> None:
    """Mutate the incoming article in-place with deduplication metadata.

    If a duplicate group is found, the article becomes a secondary source.
    Otherwise it becomes a new primary group.
    """
    # Reuse an existing group id if this article is already marked.
    existing_group = find_duplicate_group(incoming, recent_articles)
    if existing_group:
        incoming.duplicate_group_id = existing_group
        incoming.is_primary_duplicate = False
        return

    # New primary group.
    incoming.duplicate_group_id = hashlib.sha256(incoming.source_url.encode("utf-8")).hexdigest()[:16]
    incoming.is_primary_duplicate = True


def aggregate_secondary_sources(db, articles: List[Article]) -> None:
    """For each primary article, collect the source names of its duplicates.

    Call this after a batch of articles has been persisted. It reloads the
    entire duplicate group from the database so secondary source lists remain
    accurate even when duplicates arrive across multiple pipeline runs.
    """
    group_ids = {a.duplicate_group_id for a in articles if a.duplicate_group_id}
    if not group_ids:
        return

    from app.models import Article as ArticleModel

    for group_id in group_ids:
        group = (
            db.query(ArticleModel)
            .filter(ArticleModel.duplicate_group_id == group_id)
            .all()
        )
        primary = next((a for a in group if a.is_primary_duplicate), None)
        if not primary:
            continue
        secondary = sorted(
            {a.source_name for a in group if not a.is_primary_duplicate},
        )
        primary.duplicate_source_names = json.dumps(secondary) if secondary else None
        db.add(primary)
