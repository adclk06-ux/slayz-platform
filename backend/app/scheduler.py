"""
Background scheduler for periodic scraping, analysis, and institutional
briefing runs.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.briefing.engine import run_afternoon_briefing, run_morning_briefing
from app.config import get_settings
from app.database import SessionLocal
from app.market.ticker_worker import refresh_tickers, seed_history
from app.pipeline import run_ingestion_pipeline

logger = logging.getLogger("slayz.scheduler")
settings = get_settings()

_scheduler = BackgroundScheduler()


def _scheduled_job():
    db = SessionLocal()
    try:
        result = run_ingestion_pipeline(db)
        logger.info("Scheduled pipeline run complete: %s", result)
    except Exception as exc:  # noqa: BLE001
        logger.error("Scheduled pipeline run failed: %s", exc, exc_info=True)
    finally:
        db.close()


def _ticker_job():
    try:
        refresh_tickers()
    except Exception as exc:  # noqa: BLE001
        logger.error("Ticker refresh failed: %s", exc, exc_info=True)


def _morning_briefing_job():
    db = SessionLocal()
    try:
        snapshot = run_morning_briefing(db)
        logger.info("Morning briefing created: %d words", snapshot.word_count)
    except Exception as exc:  # noqa: BLE001
        logger.error("Morning briefing failed: %s", exc, exc_info=True)
    finally:
        db.close()


def _afternoon_briefing_job():
    db = SessionLocal()
    try:
        snapshot = run_afternoon_briefing(db)
        logger.info("Afternoon briefing created: %d words", snapshot.word_count)
    except Exception as exc:  # noqa: BLE001
        logger.error("Afternoon briefing failed: %s", exc, exc_info=True)
    finally:
        db.close()


def start_scheduler():
    if not _scheduler.running:
        _scheduler.add_job(
            _scheduled_job,
            "interval",
            minutes=settings.scraper_interval_minutes,
            id="ingestion_pipeline",
            replace_existing=True,
        )
        if settings.run_pipeline_on_startup:
            # Optional immediate run. Production can disable this to keep deploys fast.
            _scheduler.add_job(_scheduled_job, id="ingestion_pipeline_initial_run", replace_existing=True)

        # Market ticker loop: refresh every 30 seconds with realistic fallback data.
        # Seed history runs immediately so the terminal has data right away; the
        # interval loop then keeps it fresh without racing for row creation.
        _scheduler.add_job(
            _ticker_job,
            "interval",
            seconds=30,
            id="market_ticker_refresh",
            replace_existing=True,
        )
        _scheduler.add_job(seed_history, id="market_ticker_seed", replace_existing=True)

        # Institutional briefing engine: 08:00 and 16:00 Istanbul time.
        _scheduler.add_job(
            _morning_briefing_job,
            CronTrigger(hour=8, minute=0, timezone="Europe/Istanbul"),
            id="morning_briefing",
            replace_existing=True,
        )
        _scheduler.add_job(
            _afternoon_briefing_job,
            CronTrigger(hour=16, minute=0, timezone="Europe/Istanbul"),
            id="afternoon_briefing",
            replace_existing=True,
        )

        _scheduler.start()
        logger.info(
            "Scheduler started: ingestion=%s minute(s), market tickers=30 second(s), briefings=08:00/16:00 TR",
            settings.scraper_interval_minutes,
        )


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
