"""
Centralized application configuration.
All secrets are loaded from environment variables (.env) -- never hardcoded.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    app_secret_key: str = "dev-only-insecure-secret"
    debug: bool = True

    # Database
    database_url: str = "sqlite:///./slayz_haber.db"
    db_encryption_key: str = ""

    # Auth / RBAC
    jwt_secret_key: str = "dev-only-insecure-jwt-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    refresh_token_expire_days: int = 30
    allowed_email_domain: str = "slayz.com"
    cookie_samesite: str = "lax"

    # Real-time chat
    socketio_cors_origins: str = "*"

    # LLM
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"

    # SMTP
    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "Slayz Haber Otomasyonu"
    smtp_from: str = ""
    smtp_use_tls: bool = True
    research_team_emails: str = ""

    # Enterprise mail gateway (Resend/SendGrid slots)
    mail_provider: str = ""  # "resend" | "sendgrid" | "smtp"
    mail_api_key: str = ""
    mail_default_from: str = "noreply@slayz.local"
    mail_webhook_secret: str = ""

    # Frontend
    frontend_base_url: str = "http://localhost:3000"

    # Scraper
    # A real browser-like UA is required: Investing.com/Foreks reject the
    # generic bot UA with 403s.
    scraper_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    scraper_proxy_list: str = ""
    scraper_request_delay_seconds: int = 2
    scraper_interval_minutes: int = 1
    scheduler_enabled: bool = True
    run_pipeline_on_startup: bool = True

    # Market data
    # Never invent live prices in production. Enable only for UI development.
    market_allow_simulation: bool = False

    # CORS
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def research_team_email_list(self) -> List[str]:
        return [e.strip() for e in self.research_team_emails.split(",") if e.strip()]

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def scraper_proxy_list_parsed(self) -> List[str]:
        return [p.strip() for p in self.scraper_proxy_list.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
