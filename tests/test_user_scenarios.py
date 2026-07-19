from pathlib import Path

import pytest

from cryptopulse.agents.workflow import ContentStudioAgent
from cryptopulse.config import Settings
from cryptopulse.providers.llm import HeuristicLLMProvider
from cryptopulse.providers.meta import MetaPublisher
from cryptopulse.providers.mock import MockMarketProvider
from cryptopulse.schemas import ContentPackage, Direction, FinalPick, RiskLevel
from cryptopulse.services.qc import QualityController
from cryptopulse.services.signer import MediaURLSigner


def test_beginner_defaults_are_safe_and_cross_platform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)
    settings.ensure_directories()

    assert settings.dry_run is True
    assert settings.llm_provider == "heuristic"
    assert settings.publish_instagram is False
    assert settings.publish_facebook is False
    assert settings.publish_stories is False
    assert settings.publish_reels is False
    assert settings.retain_generated_media is True
    assert settings.media_root == Path("data/media")
    assert (tmp_path / "data/media").is_dir()
    assert (tmp_path / "data").is_dir()


async def test_dry_run_respects_instagram_only_user(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        dry_run=True,
        media_root=tmp_path,
        public_base_url="https://example.test",
        media_signing_secret="test-secret-that-is-long-enough",
        publish_instagram=True,
        publish_facebook=False,
        publish_stories=False,
        publish_reels=False,
    )
    package = ContentPackage(
        run_id="ig-only",
        direction=Direction.BULLISH,
        title="Test",
        caption="Test",
        hashtags=[],
        picks=[],
    )
    publisher = MetaPublisher(settings, MediaURLSigner(settings))
    try:
        records = await publisher.publish(package)
    finally:
        await publisher.close()

    assert [(record.platform, record.content_type) for record in records] == [
        ("instagram", "carousel")
    ]


async def test_dry_run_respects_facebook_only_user(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        dry_run=True,
        media_root=tmp_path,
        public_base_url="https://example.test",
        media_signing_secret="test-secret-that-is-long-enough",
        publish_instagram=False,
        publish_facebook=True,
        publish_stories=False,
        publish_reels=False,
    )
    package = ContentPackage(
        run_id="fb-only",
        direction=Direction.BEARISH,
        title="Test",
        caption="Test",
        hashtags=[],
        picks=[],
    )
    publisher = MetaPublisher(settings, MediaURLSigner(settings))
    try:
        records = await publisher.publish(package)
    finally:
        await publisher.close()

    assert [(record.platform, record.content_type) for record in records] == [
        ("facebook", "album")
    ]


async def test_custom_user_horizon_and_pick_count_flow_through_content_and_qc(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        dry_run=True,
        media_root=tmp_path,
        retain_generated_media=True,
        top_final_per_side=3,
        prediction_horizon_hours=12,
        publish_reels=False,
        brand_handle="@test",
    )
    market = MockMarketProvider(count=10)
    picks: list[FinalPick] = []
    for rank, asset in enumerate((await market.list_assets())[:3], start=1):
        picks.append(
            FinalPick(
                rank=rank,
                asset=asset,
                direction=Direction.BULLISH,
                final_score=80 - rank,
                confidence=70,
                risk_level=RiskLevel.MEDIUM,
                thesis="Public momentum and liquidity signals support this watch.",
                invalidation="Momentum reverses with declining volume.",
                evidence=["Public market signal"],
            )
        )

    llm = HeuristicLLMProvider()
    package = await ContentStudioAgent(settings, llm).create(
        "custom-user", Direction.BULLISH, picks
    )
    result = await QualityController(settings, llm).review(package)

    assert "Top 3" in package.title
    assert "12 Hours" in package.title
    assert "next 12 hours" in package.caption.lower()
    assert result.passed, result.errors
