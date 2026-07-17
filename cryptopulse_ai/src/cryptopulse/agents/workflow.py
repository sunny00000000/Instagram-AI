from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import UTC, datetime, timedelta

from cryptopulse.config import Settings
from cryptopulse.providers.base import LLMProvider, MarketProvider, NewsProvider
from cryptopulse.providers.meta import MetaPublisher
from cryptopulse.schemas import (
    ContentPackage,
    Direction,
    FinalPick,
    MarketAsset,
    MarketHistory,
    NewsItem,
    PreliminarySignal,
    ProjectProfile,
    PublishRecord,
    QCResult,
)
from cryptopulse.services.qc import QualityController
from cryptopulse.services.render import MediaRenderer
from cryptopulse.services.repository import Repository
from cryptopulse.services.scoring import create_preliminary_signals, select_final_picks
from cryptopulse.services.video import ReelBuilder

logger = logging.getLogger(__name__)


class MarketManagerAgent:
    def __init__(self, provider: MarketProvider, settings: Settings):
        self.provider = provider
        self.settings = settings

    async def scan(self) -> list[MarketAsset]:
        return await self.provider.list_assets()

    def shortlist(
        self, assets: list[MarketAsset]
    ) -> tuple[list[PreliminarySignal], list[PreliminarySignal]]:
        return create_preliminary_signals(assets, self.settings.top_preliminary_per_side)


class NewsManagerAgent:
    def __init__(self, provider: NewsProvider):
        self.provider = provider

    async def scan(self) -> list[NewsItem]:
        return await self.provider.fetch_news()


class ResearchManagerAgent:
    def __init__(
        self,
        market_provider: MarketProvider,
        llm: LLMProvider,
        repository: Repository,
        settings: Settings,
    ):
        self.market_provider = market_provider
        self.llm = llm
        self.repository = repository
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_workers)

    async def research(
        self,
        signals: list[PreliminarySignal],
        news: list[NewsItem],
        direction: Direction,
    ) -> tuple[list, dict[str, MarketHistory]]:
        assets = [signal.asset for signal in signals]
        histories, profiles = await asyncio.gather(
            self._load_histories(assets),
            self._load_profiles(assets),
        )
        analyses: list = []
        for offset in range(0, len(assets), self.settings.llm_batch_size):
            batch = assets[offset : offset + self.settings.llm_batch_size]
            batch_analyses = await self.llm.analyze_batch(batch, news, profiles, direction)
            analyses.extend(batch_analyses)
        return analyses, histories

    async def _load_histories(self, assets: list[MarketAsset]) -> dict[str, MarketHistory]:
        async def load(asset: MarketAsset) -> tuple[str, MarketHistory]:
            async with self._semaphore:
                try:
                    return asset.asset_id, await self.market_provider.get_history(asset.asset_id)
                except Exception as exc:
                    logger.warning(
                        "History load failed for %s: %s",
                        asset.asset_id,
                        exc,
                        extra={"run_id": "research"},
                    )
                    return asset.asset_id, MarketHistory(asset_id=asset.asset_id)

        return dict(await asyncio.gather(*(load(asset) for asset in assets)))

    async def _load_profiles(self, assets: list[MarketAsset]) -> dict[str, ProjectProfile]:
        async def load(asset: MarketAsset) -> tuple[str, ProjectProfile]:
            cached = self.repository.get_profile(asset.asset_id)
            if cached:
                return asset.asset_id, cached
            async with self._semaphore:
                try:
                    profile = await self.market_provider.get_project_profile(asset.asset_id)
                    self.repository.upsert_profile(profile)
                    return asset.asset_id, profile
                except Exception as exc:
                    logger.warning(
                        "Profile load failed for %s: %s",
                        asset.asset_id,
                        exc,
                        extra={"run_id": "research"},
                    )
                    return asset.asset_id, ProjectProfile(asset_id=asset.asset_id)

        return dict(await asyncio.gather(*(load(asset) for asset in assets)))


class DecisionBoardAgent:
    def __init__(self, settings: Settings):
        self.settings = settings

    def decide(
        self,
        signals: list[PreliminarySignal],
        analyses: list,
        histories: dict[str, MarketHistory],
    ) -> list[FinalPick]:
        return select_final_picks(
            signals,
            analyses,
            histories,
            self.settings.top_final_per_side,
        )


class ContentStudioAgent:
    def __init__(self, settings: Settings, llm: LLMProvider):
        self.settings = settings
        self.llm = llm
        self.renderer = MediaRenderer(settings)
        self.reel_builder = ReelBuilder()

    async def create(
        self, run_id: str, direction: Direction, picks: list[FinalPick]
    ) -> ContentPackage:
        label = "Bullish Watch" if direction == Direction.BULLISH else "Bearish Risk"
        title = f"Top 5 Crypto {label}: Next 6 Hours"
        caption = self._caption(direction, picks)
        caption = await self.llm.improve_caption(caption, direction)
        package = ContentPackage(
            run_id=run_id,
            direction=direction,
            title=title,
            caption=caption,
            hashtags=self._hashtags(direction, picks),
            picks=picks,
        )
        package = self.renderer.render_package(package)
        return self.reel_builder.build(package) if self.settings.publish_reels else package

    def _caption(self, direction: Direction, picks: list[FinalPick]) -> str:
        label = "Bullish Watch" if direction == Direction.BULLISH else "Bearish Risk"
        action = (
            "positive momentum signals"
            if direction == Direction.BULLISH
            else "downside risk signals"
        )
        lines = [
            f"Top 5 Crypto {label} for the next 6 hours",
            "",
            f"These assets ranked highest for {action} using public price, liquidity, news and project signals available at generation time.",
            "",
        ]
        for pick in picks:
            lines.extend(
                [
                    f"{pick.rank}. ${pick.asset.symbol} — score {pick.final_score:.0f}/100 · confidence {pick.confidence:.0f}% · risk {pick.risk_level.value}",
                    pick.thesis,
                    f"Invalidation: {pick.invalidation}",
                    "",
                ]
            )
        lines.extend(
            [
                "Market conditions can change immediately. Verify all information before acting.",
                self.settings.disclaimer,
            ]
        )
        return "\n".join(lines).strip()

    @staticmethod
    def _hashtags(direction: Direction, picks: list[FinalPick]) -> list[str]:
        base = [
            "CryptoMarket",
            "CryptoAnalysis",
            "DigitalAssets",
            "MarketIntelligence",
            "RiskManagement",
            "Blockchain",
            "CryptoNews",
            "DYOR",
        ]
        base.append("BullishWatch" if direction == Direction.BULLISH else "BearishRisk")
        base.extend(pick.asset.symbol for pick in picks)
        return list(dict.fromkeys(base))[:18]


class QualityGateAgent:
    def __init__(self, controller: QualityController):
        self.controller = controller

    async def review(self, package: ContentPackage) -> QCResult:
        return await self.controller.review(package)


class PublishingManagerAgent:
    def __init__(self, publisher: MetaPublisher):
        self.publisher = publisher

    async def publish(self, package: ContentPackage) -> list[PublishRecord]:
        return await self.publisher.publish(package)


class LearningAgent:
    def __init__(self, market_provider: MarketProvider, repository: Repository):
        self.market_provider = market_provider
        self.repository = repository

    async def evaluate_due_predictions(self) -> int:
        due = self.repository.due_predictions()
        evaluated = 0
        for prediction in due:
            try:
                price = await self.market_provider.get_current_price(prediction.asset_id)
                if price is not None:
                    self.repository.save_evaluation(prediction.id, price)
                    evaluated += 1
            except Exception as exc:
                logger.warning(
                    "Prediction evaluation failed for %s: %s",
                    prediction.asset_id,
                    exc,
                    extra={"run_id": "learning"},
                )
        return evaluated


class CleanupAgent:
    def __init__(self, settings: Settings):
        self.settings = settings

    def cleanup_expired_media(self) -> int:
        if self.settings.retain_generated_media:
            return 0
        cutoff = datetime.now(UTC) - timedelta(hours=self.settings.media_delete_grace_hours)
        deleted = 0
        root = self.settings.media_root
        if not root.exists():
            return 0
        for run_dir in root.iterdir():
            if not run_dir.is_dir():
                continue
            modified = datetime.fromtimestamp(run_dir.stat().st_mtime, tz=UTC)
            if modified <= cutoff:
                shutil.rmtree(run_dir, ignore_errors=True)
                deleted += 1
        return deleted

    def delete_run_media_now(self, run_id: str) -> None:
        if self.settings.retain_generated_media:
            return
        run_dir = self.settings.media_root / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)
