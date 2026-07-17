from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class Direction(StrEnum):
    BULLISH = "bullish_watch"
    BEARISH = "bearish_risk"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class MarketAsset(BaseModel):
    asset_id: str
    symbol: str
    name: str
    current_price: float
    market_cap: float = 0
    market_cap_rank: int | None = None
    volume_24h: float = 0
    change_1h: float = 0
    change_24h: float = 0
    change_7d: float = 0
    circulating_supply: float | None = None
    total_supply: float | None = None
    ath_change_percentage: float | None = None
    last_updated: datetime = Field(default_factory=utc_now)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()

    @property
    def liquidity_ratio(self) -> float:
        if self.market_cap <= 0:
            return 0.0
        return self.volume_24h / self.market_cap


class MarketHistory(BaseModel):
    asset_id: str
    prices: list[tuple[int, float]] = Field(default_factory=list)
    volumes: list[tuple[int, float]] = Field(default_factory=list)


class ProjectProfile(BaseModel):
    asset_id: str
    official_url: str | None = None
    description: str = ""
    categories: list[str] = Field(default_factory=list)
    genesis_date: str | None = None
    hashing_algorithm: str | None = None
    source_fingerprint: str = ""


class NewsItem(BaseModel):
    title: str
    summary: str = ""
    url: HttpUrl | str
    source: str
    published_at: datetime = Field(default_factory=utc_now)
    categories: list[str] = Field(default_factory=list)
    related_asset_ids: list[str] = Field(default_factory=list)


class PreliminarySignal(BaseModel):
    asset: MarketAsset
    direction: Direction
    preliminary_score: float
    liquidity_score: float
    momentum_score: float
    volatility_score: float
    reasons: list[str] = Field(default_factory=list)


class DeepAnalysis(BaseModel):
    asset_id: str
    direction: Direction
    technical_score: float = Field(ge=0, le=100)
    news_score: float = Field(ge=0, le=100)
    fundamental_score: float = Field(ge=0, le=100)
    public_intelligence_score: float = Field(ge=0, le=100)
    contradiction_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    thesis: str
    invalidation: str
    evidence: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class FinalPick(BaseModel):
    rank: int
    asset: MarketAsset
    direction: Direction
    final_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    thesis: str
    invalidation: str
    evidence: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    sparkline: list[float] = Field(default_factory=list)


class ContentAsset(BaseModel):
    content_type: str
    direction: Direction
    path: Path
    mime_type: str
    width: int | None = None
    height: int | None = None
    slide_index: int | None = None


class ContentPackage(BaseModel):
    run_id: str
    direction: Direction
    title: str
    caption: str
    hashtags: list[str]
    picks: list[FinalPick]
    assets: list[ContentAsset] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class QCResult(BaseModel):
    passed: bool
    checks: dict[str, bool]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PublishRecord(BaseModel):
    platform: str
    content_type: str
    direction: Direction
    success: bool
    external_id: str | None = None
    error: str | None = None
    published_at: datetime | None = None


class RunSummary(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "running"
    market_asset_count: int = 0
    news_item_count: int = 0
    bullish_picks: list[FinalPick] = Field(default_factory=list)
    bearish_picks: list[FinalPick] = Field(default_factory=list)
    qc_results: dict[str, QCResult] = Field(default_factory=dict)
    publish_records: list[PublishRecord] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
