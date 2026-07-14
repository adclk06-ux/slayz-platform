"""
Database engine/session setup with strict connection pooling and lightweight
auto-migration for the SQLite development environment.
"""
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

logger = logging.getLogger("slayz.database")
settings = get_settings()

is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

if is_sqlite:
    # SQLite does not support pool_size/max_overflow (uses SingletonThreadPool/NullPool).
    engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
else:
    engine = create_engine(
        settings.database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Columns added for institutional-grade features. Format: (column_name, type, default).
_ARTICLE_COLUMNS = [
    ("extracted_tickers", "TEXT", None),
    ("market_cap_usd", "VARCHAR(64)", None),
    ("is_mega_cap", "BOOLEAN", "0"),
    ("macro_region", "VARCHAR(8)", None),
    ("macro_indicator", "VARCHAR(32)", None),
    ("duplicate_group_id", "VARCHAR(64)", None),
    ("is_primary_duplicate", "BOOLEAN", "1"),
    ("duplicate_source_names", "TEXT", None),
]

# Workspace chat / presence columns.
_USER_COLUMNS = [
    ("avatar_url", "VARCHAR(1024)", None),
    ("status", "VARCHAR(64)", "'available'"),
    ("last_seen_at", "DATETIME", None),
    ("updated_at", "DATETIME", None),
]

_CHAT_MESSAGE_COLUMNS = [
    ("recipient_id", "VARCHAR", None),
]

_INBOX_MESSAGE_COLUMNS = [
    ("recipient_id", "VARCHAR", None),
]


def _add_missing_columns(inspector, conn, table: str, columns) -> None:
    existing_cols = {c["name"] for c in inspector.get_columns(table)}
    for col_name, col_type, default in columns:
        if col_name in existing_cols:
            continue
        default_clause = f"DEFAULT {default}" if default is not None else ""
        sql = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type} {default_clause}"
        conn.execute(text(sql.strip()))
        conn.commit()
        logger.info("Added column %s.%s", table, col_name)


def _migrate_sqlite() -> None:
    """Add missing columns/tables when running against SQLite in development.

    Production deployments should use Alembic migrations; this helper keeps local
    development friction low while the schema evolves rapidly.
    """
    if not is_sqlite:
        return

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Ensure new institutional tables exist.
    if "briefing_snapshots" not in existing_tables:
        Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["briefing_snapshots"]])
        logger.info("Created briefing_snapshots table")

    with engine.connect() as conn:
        if "articles" in existing_tables:
            _add_missing_columns(inspector, conn, "articles", _ARTICLE_COLUMNS)
        if "users" in existing_tables:
            _add_missing_columns(inspector, conn, "users", _USER_COLUMNS)
        if "chat_messages" in existing_tables:
            _add_missing_columns(inspector, conn, "chat_messages", _CHAT_MESSAGE_COLUMNS)
        if "inbox_messages" in existing_tables:
            _add_missing_columns(inspector, conn, "inbox_messages", _INBOX_MESSAGE_COLUMNS)


def ensure_schema() -> None:
    """Create/migrate the schema at startup."""
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
