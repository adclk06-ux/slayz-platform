"""
LLM analysis pipeline: sends raw scraped articles to the configured LLM
(OpenAI GPT-4o by default) and returns a structured, engaging rewrite.
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI, OpenAIError

from app.config import get_settings
from app.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.models import NewsCategory

logger = logging.getLogger("slayz.llm")
settings = get_settings()


@dataclass
class AnalysisResult:
    title: str
    summary: str
    category: NewsCategory
    sentiment: str


_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Set it in the .env file before running the LLM pipeline."
            )
        import httpx

        # Custom http_client avoids httpx 0.28+ 'proxies' kwarg incompatibility.
        _client = OpenAI(
            api_key=settings.openai_api_key,
            http_client=httpx.Client(timeout=60.0),
        )
    return _client


def _safe_category(value: str) -> NewsCategory:
    try:
        return NewsCategory(value.lower().strip())
    except ValueError:
        logger.warning("Unknown category '%s' returned by LLM, defaulting to GENERAL", value)
        return NewsCategory.GENERAL


def analyze_article(source_name: str, raw_title: str, raw_content: str) -> Optional[AnalysisResult]:
    """Calls the LLM to rewrite/summarize a raw article.

    Returns None when no API key is configured so the ingestion pipeline keeps
    running in demo/local mode without raising and spamming the logs. Real LLM
    errors still propagate.
    """
    if not settings.openai_api_key:
        logger.info("OPENAI_API_KEY not configured; skipping LLM analysis for '%s'", raw_title)
        return None

    user_prompt = USER_PROMPT_TEMPLATE.format(
        source_name=source_name, raw_title=raw_title, raw_content=raw_content[:12000]
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return AnalysisResult(
            title=data["title"],
            summary=data["summary"],
            category=_safe_category(data.get("category", "general")),
            sentiment=data.get("sentiment", "neutral"),
        )
    except (OpenAIError, json.JSONDecodeError, KeyError) as exc:
        logger.error("LLM analysis failed for '%s': %s", raw_title, exc, exc_info=True)
        raise
