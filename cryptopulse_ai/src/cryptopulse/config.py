from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    dry_run: bool = True
    timezone: str = "UTC"
    schedule_hours: str = "0,6,12,18"
    run_on_startup: bool = False
    max_concurrent_workers: int = Field(default=4, ge=1, le=32)
    max_market_pages: int = Field(default=80, ge=1, le=1000)
    market_page_size: int = Field(default=250, ge=10, le=250)
    min_market_cap_usd: float = Field(default=1_000_000, ge=0)
    min_volume_24h_usd: float = Field(default=100_000, ge=0)
    top_preliminary_per_side: int = Field(default=15, ge=5, le=100)
    top_final_per_side: int = Field(default=5, ge=1, le=20)
    prediction_horizon_hours: int = Field(default=6, ge=1, le=168)

    market_provider: str = "coingecko"
    coingecko_api_key: str | None = None
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    coingecko_request_interval_seconds: float = Field(default=2.2, ge=0.1, le=60)
    news_provider: str = "hybrid"
    news_rss_feeds: str = ("https://www.coindesk.com/arc/outboundfeeds/rss/,") + (
        "https://cointelegraph.com/rss,https://decrypt.co/feed"
    )
    gdelt_max_records: int = Field(default=75, ge=10, le=250)

    llm_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    llm_batch_size: int = Field(default=10, ge=1, le=30)
    llm_max_concurrency: int = Field(default=2, ge=1, le=10)
    llm_timeout_seconds: int = Field(default=90, ge=10, le=600)

    meta_graph_version: str = "v25.0"
    meta_access_token: str | None = None
    instagram_user_id: str | None = None
    facebook_page_id: str | None = None
    publish_instagram: bool = True
    publish_facebook: bool = True
    publish_stories: bool = True
    publish_reels: bool = True

    public_base_url: str | None = None
    media_signing_secret: str = "change-this-to-a-long-random-secret"
    media_url_ttl_seconds: int = Field(default=86400, ge=300, le=604800)
    media_delete_grace_hours: int = Field(default=24, ge=1, le=168)

    database_url: str = "sqlite:///./data/cryptopulse.db"
    media_root: Path = Path("./data/media")
    retain_raw_data: bool = False
    retain_generated_media: bool = False
    project_profile_refresh_hours: int = Field(default=168, ge=1, le=8760)

    brand_name: str = "CryptoPulse AI"
    brand_handle: str = "@yourhandle"
    disclaimer: str = (
        "Educational market intelligence only. Not financial advice. "
        "Crypto assets are highly volatile."
    )

    excluded_symbols: str = (
        "usdt,usdc,dai,tusd,fdusd,usde,pyusd,usdd,usdp,gusd,frax,lusd,busd,eurc,eurc"
    )

    @field_validator("public_base_url")
    @classmethod
    def normalize_public_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value.rstrip("/")

    @property
    def schedule_hour_list(self) -> list[int]:
        values = [int(item.strip()) for item in self.schedule_hours.split(",") if item.strip()]
        if any(hour < 0 or hour > 23 for hour in values):
            raise ValueError("SCHEDULE_HOURS must contain hours between 0 and 23")
        return sorted(set(values))

    @property
    def rss_feed_list(self) -> list[str]:
        return [item.strip() for item in self.news_rss_feeds.split(",") if item.strip()]

    @property
    def excluded_symbol_set(self) -> set[str]:
        return {item.strip().lower() for item in self.excluded_symbols.split(",") if item.strip()}

    def ensure_directories(self) -> None:
        self.media_root.mkdir(parents=True, exist_ok=True)
        Path("./logs").mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            database_path = Path(self.database_url.removeprefix("sqlite:///"))
            database_path.parent.mkdir(parents=True, exist_ok=True)

    def validate_live_publish_requirements(self) -> list[str]:
        missing: list[str] = []
        if self.dry_run:
            return missing
        if not self.meta_access_token:
            missing.append("META_ACCESS_TOKEN")
        if self.publish_instagram and not self.instagram_user_id:
            missing.append("INSTAGRAM_USER_ID")
        if self.publish_facebook and not self.facebook_page_id:
            missing.append("FACEBOOK_PAGE_ID")
        if not self.public_base_url:
            missing.append("PUBLIC_BASE_URL")
        if self.media_signing_secret == "change-this-to-a-long-random-secret":
            missing.append("MEDIA_SIGNING_SECRET")
        return missing


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
