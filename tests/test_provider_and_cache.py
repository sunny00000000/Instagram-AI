from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptopulse.config import Settings
from cryptopulse.db import Database, ProjectProfileRow
from cryptopulse.providers.coingecko import CoinGeckoProvider
from cryptopulse.schemas import ProjectProfile
from cryptopulse.services.repository import Repository


def test_coingecko_hourly_points_keeps_latest_sample_per_hour():
    points = [
        [1_000, 1.0],
        [3_599_000, 2.0],
        [3_600_000, 3.0],
        [7_100_000, 4.0],
        [7_200_000, 5.0],
    ]
    assert CoinGeckoProvider._hourly_points(points) == [
        (3_599_000, 2.0),
        (7_100_000, 4.0),
        (7_200_000, 5.0),
    ]


def test_project_profile_cache_refreshes_when_stale(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'cache.db'}",
        media_root=tmp_path / "media",
        project_profile_refresh_hours=24,
    )
    database = Database(settings)
    database.create_all()
    repository = Repository(database, settings)
    profile = ProjectProfile(
        asset_id="bitcoin",
        description="Bitcoin profile",
        source_fingerprint="fingerprint",
    )
    repository.upsert_profile(profile)
    assert repository.get_profile("bitcoin") == profile

    with database.session() as session:
        row = session.get(ProjectProfileRow, "bitcoin")
        assert row is not None
        row.updated_at = datetime.now(UTC) - timedelta(hours=25)
        session.commit()

    assert repository.get_profile("bitcoin") is None
