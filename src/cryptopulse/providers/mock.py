from __future__ import annotations

from datetime import UTC, datetime

from cryptopulse.providers.base import MarketProvider, NewsProvider
from cryptopulse.schemas import MarketAsset, MarketHistory, NewsItem, ProjectProfile


class MockMarketProvider(MarketProvider):
    def __init__(self, count: int = 60):
        self.assets = []
        for index in range(count):
            bullish = index < count // 2
            sign = 1 if bullish else -1
            self.assets.append(
                MarketAsset(
                    asset_id=f"asset-{index}",
                    symbol=f"c{index}",
                    name=f"Coin {index}",
                    current_price=1 + index * 0.25,
                    market_cap=1_000_000_000 - index * 5_000_000,
                    market_cap_rank=index + 1,
                    volume_24h=50_000_000 + index * 500_000,
                    change_1h=sign * (1 + index * 0.12),
                    change_24h=sign * (2 + index * 0.18),
                    change_7d=sign * (3 + index * 0.2),
                    last_updated=datetime.now(UTC),
                )
            )

    async def list_assets(self) -> list[MarketAsset]:
        return list(self.assets)

    async def get_history(self, asset_id: str) -> MarketHistory:
        index = int(asset_id.split("-")[-1])
        sign = 1 if index < len(self.assets) // 2 else -1
        prices = [(hour * 3_600_000, 10 + sign * hour * 0.12 + index * 0.05) for hour in range(24)]
        volumes = [(hour * 3_600_000, float(1_000_000 + hour * 20_000)) for hour in range(24)]
        return MarketHistory(asset_id=asset_id, prices=prices, volumes=volumes)

    async def get_project_profile(self, asset_id: str) -> ProjectProfile:
        return ProjectProfile(
            asset_id=asset_id,
            official_url="https://example.com",
            description=f"Public project profile for {asset_id}.",
            categories=["sample"],
            source_fingerprint=asset_id,
        )

    async def get_current_price(self, asset_id: str) -> float | None:
        for asset in self.assets:
            if asset.asset_id == asset_id:
                return asset.current_price * 1.01
        return None


class MockNewsProvider(NewsProvider):
    async def fetch_news(self) -> list[NewsItem]:
        return [
            NewsItem(
                title="Coin 0 announces ecosystem upgrade",
                summary="The project published a public upgrade roadmap.",
                url="https://example.com/news/upgrade",
                source="Example News",
            ),
            NewsItem(
                title="Coin 59 faces service outage",
                summary="The network reported a temporary public outage.",
                url="https://example.com/news/outage",
                source="Example News",
            ),
        ]
