from __future__ import annotations

from datetime import UTC, timedelta

from sqlalchemy import select

from cryptopulse.config import Settings
from cryptopulse.db import Database, PredictionRow, ProjectProfileRow, PublishRow, RunRow
from cryptopulse.schemas import ProjectProfile, PublishRecord, RunSummary, utc_now


class Repository:
    def __init__(self, database: Database, settings: Settings):
        self.database = database
        self.settings = settings

    def start_run(self, summary: RunSummary) -> None:
        with self.database.session() as session:
            session.merge(
                RunRow(
                    run_id=summary.run_id,
                    status=summary.status,
                    started_at=summary.started_at,
                    market_asset_count=0,
                    news_item_count=0,
                    summary_json={},
                )
            )
            session.commit()

    def finish_run(self, summary: RunSummary) -> None:
        with self.database.session() as session:
            row = session.get(RunRow, summary.run_id)
            if row is None:
                row = RunRow(
                    run_id=summary.run_id,
                    status=summary.status,
                    started_at=summary.started_at,
                )
                session.add(row)
            row.status = summary.status
            row.completed_at = summary.completed_at
            row.market_asset_count = summary.market_asset_count
            row.news_item_count = summary.news_item_count
            row.summary_json = summary.model_dump(mode="json")
            row.error_text = "\n".join(summary.errors) or None
            session.commit()

    def store_predictions(self, summary: RunSummary) -> None:
        due_at = summary.started_at + timedelta(hours=self.settings.prediction_horizon_hours)
        with self.database.session() as session:
            for pick in [*summary.bullish_picks, *summary.bearish_picks]:
                session.add(
                    PredictionRow(
                        run_id=summary.run_id,
                        asset_id=pick.asset.asset_id,
                        symbol=pick.asset.symbol,
                        direction=pick.direction.value,
                        rank=pick.rank,
                        confidence=pick.confidence,
                        final_score=pick.final_score,
                        price_at_prediction=pick.asset.current_price,
                        predicted_at=summary.started_at,
                        horizon_hours=self.settings.prediction_horizon_hours,
                        evaluation_due_at=due_at,
                    )
                )
            session.commit()

    def store_publish_records(self, run_id: str, records: list[PublishRecord]) -> None:
        with self.database.session() as session:
            for record in records:
                session.add(
                    PublishRow(
                        run_id=run_id,
                        platform=record.platform,
                        content_type=record.content_type,
                        direction=record.direction.value,
                        success=record.success,
                        external_id=record.external_id,
                        error_text=record.error,
                        created_at=record.published_at or utc_now(),
                    )
                )
            session.commit()

    def get_profile(self, asset_id: str) -> ProjectProfile | None:
        with self.database.session() as session:
            row = session.get(ProjectProfileRow, asset_id)
            if row is None:
                return None
            updated_at = row.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
            refresh_before = utc_now() - timedelta(
                hours=self.settings.project_profile_refresh_hours
            )
            if updated_at < refresh_before:
                return None
            return ProjectProfile.model_validate(row.profile_json)

    def upsert_profile(self, profile: ProjectProfile) -> None:
        with self.database.session() as session:
            session.merge(
                ProjectProfileRow(
                    asset_id=profile.asset_id,
                    source_fingerprint=profile.source_fingerprint,
                    profile_json=profile.model_dump(mode="json"),
                    updated_at=utc_now(),
                )
            )
            session.commit()

    def due_predictions(self) -> list[PredictionRow]:
        with self.database.session() as session:
            result = session.scalars(
                select(PredictionRow).where(
                    PredictionRow.evaluated.is_(False),
                    PredictionRow.evaluation_due_at <= utc_now(),
                )
            )
            return list(result)

    def save_evaluation(self, prediction_id: int, price: float) -> None:
        with self.database.session() as session:
            row = session.get(PredictionRow, prediction_id)
            if row is None or row.evaluated:
                return
            actual_change = ((price - row.price_at_prediction) / row.price_at_prediction) * 100
            bullish = row.direction == "bullish_watch"
            row.price_at_evaluation = price
            row.actual_change_pct = actual_change
            row.correct = actual_change > 0 if bullish else actual_change < 0
            row.evaluated = True
            session.commit()
