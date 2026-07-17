from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from cryptopulse.agents.workflow import (
    CleanupAgent,
    ContentStudioAgent,
    DecisionBoardAgent,
    LearningAgent,
    MarketManagerAgent,
    NewsManagerAgent,
    PublishingManagerAgent,
    QualityGateAgent,
    ResearchManagerAgent,
)
from cryptopulse.config import Settings
from cryptopulse.schemas import Direction, RunSummary
from cryptopulse.services.repository import Repository
from cryptopulse.services.run_lock import RunLock

logger = logging.getLogger(__name__)


class CEOOrchestrator:
    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        market_manager: MarketManagerAgent,
        news_manager: NewsManagerAgent,
        research_manager: ResearchManagerAgent,
        decision_board: DecisionBoardAgent,
        content_studio: ContentStudioAgent,
        quality_gate: QualityGateAgent,
        publishing_manager: PublishingManagerAgent,
        learning_agent: LearningAgent,
        cleanup_agent: CleanupAgent,
    ):
        self.settings = settings
        self.repository = repository
        self.market_manager = market_manager
        self.news_manager = news_manager
        self.research_manager = research_manager
        self.decision_board = decision_board
        self.content_studio = content_studio
        self.quality_gate = quality_gate
        self.publishing_manager = publishing_manager
        self.learning_agent = learning_agent
        self.cleanup_agent = cleanup_agent

    async def run_once(self) -> RunSummary:
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        summary = RunSummary(run_id=run_id, started_at=datetime.now(UTC))
        self.repository.start_run(summary)
        with RunLock():
            try:
                missing = self.settings.validate_live_publish_requirements()
                if missing:
                    raise RuntimeError(
                        "Live publishing configuration is incomplete: " + ", ".join(missing)
                    )

                await self.learning_agent.evaluate_due_predictions()
                assets, news = await asyncio.gather(
                    self.market_manager.scan(),
                    self.news_manager.scan(),
                )
                summary.market_asset_count = len(assets)
                summary.news_item_count = len(news)
                if len(assets) < self.settings.top_preliminary_per_side * 2:
                    raise RuntimeError(
                        f"Insufficient eligible assets returned by market provider: {len(assets)}"
                    )

                bullish_signals, bearish_signals = self.market_manager.shortlist(assets)
                bullish_research, bearish_research = await asyncio.gather(
                    self.research_manager.research(bullish_signals, news, Direction.BULLISH),
                    self.research_manager.research(bearish_signals, news, Direction.BEARISH),
                )
                bullish_analyses, bullish_histories = bullish_research
                bearish_analyses, bearish_histories = bearish_research

                summary.bullish_picks = self.decision_board.decide(
                    bullish_signals, bullish_analyses, bullish_histories
                )
                summary.bearish_picks = self.decision_board.decide(
                    bearish_signals, bearish_analyses, bearish_histories
                )
                if len(summary.bullish_picks) != self.settings.top_final_per_side:
                    raise RuntimeError("Decision board did not produce five bullish picks")
                if len(summary.bearish_picks) != self.settings.top_final_per_side:
                    raise RuntimeError("Decision board did not produce five bearish picks")

                packages = await asyncio.gather(
                    self.content_studio.create(run_id, Direction.BULLISH, summary.bullish_picks),
                    self.content_studio.create(run_id, Direction.BEARISH, summary.bearish_picks),
                )
                for package in packages:
                    qc_result = None
                    for attempt in range(1, 3):
                        qc_result = await self.quality_gate.review(package)
                        if qc_result.passed:
                            break
                        logger.warning(
                            "QC attempt %s failed: %s",
                            attempt,
                            qc_result.errors,
                            extra={"run_id": run_id},
                        )
                        if attempt < 2:
                            package = await self.content_studio.create(
                                run_id, package.direction, package.picks
                            )
                    assert qc_result is not None
                    summary.qc_results[package.direction.value] = qc_result
                    if not qc_result.passed:
                        raise RuntimeError(
                            f"QC failed for {package.direction.value}: {qc_result.errors}"
                        )
                    records = await self.publishing_manager.publish(package)
                    summary.publish_records.extend(records)

                if not all(record.success for record in summary.publish_records):
                    failures = [
                        f"{record.platform}/{record.content_type}: {record.error}"
                        for record in summary.publish_records
                        if not record.success
                    ]
                    raise RuntimeError("Publishing failed: " + "; ".join(failures))

                self.repository.store_predictions(summary)
                self.repository.store_publish_records(run_id, summary.publish_records)
                summary.status = "completed"
                summary.metrics["media_cleanup_grace_hours"] = (
                    self.settings.media_delete_grace_hours
                )
            except Exception as exc:
                logger.exception("Pipeline run failed", extra={"run_id": run_id})
                summary.status = "failed"
                summary.errors.append(str(exc))
            finally:
                summary.completed_at = datetime.now(UTC)
                self.repository.finish_run(summary)
                self.cleanup_agent.cleanup_expired_media()
        return summary
