from pathlib import Path

from PIL import Image

from cryptopulse.config import Settings
from cryptopulse.providers.mock import MockMarketProvider
from cryptopulse.schemas import ContentPackage, Direction, FinalPick, RiskLevel
from cryptopulse.services.render import MediaRenderer


async def test_renderer_creates_correct_dimensions(tmp_path: Path):
    settings = Settings(
        dry_run=True,
        media_root=tmp_path,
        retain_generated_media=True,
        brand_handle="@test",
        publish_reels=False,
    )
    market = MockMarketProvider(count=10)
    picks = []
    for rank, asset in enumerate((await market.list_assets())[:5], start=1):
        history = await market.get_history(asset.asset_id)
        picks.append(
            FinalPick(
                rank=rank,
                asset=asset,
                direction=Direction.BULLISH,
                final_score=80 - rank,
                confidence=70,
                risk_level=RiskLevel.MEDIUM,
                thesis="Public momentum and liquidity signals are positive for this six-hour watch.",
                invalidation="Momentum reverses and volume declines.",
                evidence=["Public market signal"],
                sparkline=[price for _, price in history.prices],
            )
        )
    package = ContentPackage(
        run_id="render-test",
        direction=Direction.BULLISH,
        title="Top 5 Crypto Bullish Watch · Next 6 Hours",
        caption="Six-hour outlook. Not financial advice. C0 C1 C2 C3 C4",
        hashtags=["Crypto"],
        picks=picks,
    )
    rendered = MediaRenderer(settings).render_package(package)
    carousels = [asset for asset in rendered.assets if asset.content_type == "carousel"]
    stories = [asset for asset in rendered.assets if asset.content_type == "story"]
    assert len(carousels) == 7
    assert len(stories) == 6
    for asset in carousels:
        with Image.open(asset.path) as image:
            assert image.size == (1080, 1350)
    for asset in stories:
        with Image.open(asset.path) as image:
            assert image.size == (1080, 1920)
