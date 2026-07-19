import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptopulse.agents.workflow import CleanupAgent
from cryptopulse.config import Settings


def test_cleanup_removes_expired_run_directory(tmp_path: Path):
    old = tmp_path / "old-run"
    fresh = tmp_path / "fresh-run"
    old.mkdir()
    fresh.mkdir()
    (old / "a.png").write_bytes(b"x")
    old_time = (datetime.now(UTC) - timedelta(hours=48)).timestamp()
    os.utime(old, (old_time, old_time))
    settings = Settings(
        dry_run=True,
        media_root=tmp_path,
        media_delete_grace_hours=24,
        retain_generated_media=False,
    )
    deleted = CleanupAgent(settings).cleanup_expired_media()
    assert deleted == 1
    assert not old.exists()
    assert fresh.exists()
