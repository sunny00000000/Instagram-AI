from pathlib import Path

from cryptopulse.config import Settings
from cryptopulse.runtime import create_runtime


async def test_complete_mock_pipeline(tmp_path: Path):
    settings = Settings(
        app_env="test",
        dry_run=True,
        llm_provider="heuristic",
        media_root=tmp_path / "media",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        retain_generated_media=True,
        brand_handle="@test",
        publish_instagram=True,
        publish_facebook=True,
        publish_stories=True,
        publish_reels=False,
    )
    runtime = create_runtime(settings, use_mock=True)
    try:
        summary = await runtime.orchestrator.run_once()
    finally:
        await runtime.close()
    assert summary.status == "completed", summary.errors
    assert len(summary.bullish_picks) == 5
    assert len(summary.bearish_picks) == 5
    assert all(result.passed for result in summary.qc_results.values())
    assert len(summary.publish_records) == 16
    assert all(record.success for record in summary.publish_records)
    assert list((tmp_path / "media" / summary.run_id).rglob("*.png"))
