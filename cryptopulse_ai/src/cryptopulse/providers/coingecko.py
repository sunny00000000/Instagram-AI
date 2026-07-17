from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from cryptopulse.config import Settings
from cryptopulse.providers.base import MarketProvider
from cryptopulse.schemas import MarketAsset, MarketHistory, ProjectProfile

logger = logging.getLogger(__name__)


class CoinGeckoProvider(MarketProvider):
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        headers = {"accept": "application/json", "user-agent": "CryptoPulseAI/0.1"}
        if settings.coingecko_api_key:
            headers["x-cg-demo-api-key"] = settings.coingecko_api_key
        self.client = client or httpx.AsyncClient(
            base_url=settings.coingecko_base_url,
            headers=headers,
            timeout=httpx.Timeout(45.0),
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )
        self._owns_client = client is None
        self._request_lock = asyncio.Lock()

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, ValueError)),
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=1, max=20),
        reraise=True,
    )
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        # CoinGecko public/demo plans are rate limited. Serialize requests and
        # keep a configurable interval so pagination and deep research do not
        # burst into HTTP 429 responses.
        async with self._request_lock:
            response = await self.client.get(path, params=params)
            response.raise_for_status()
            payload = response.json()
            await asyncio.sleep(self.settings.coingecko_request_interval_seconds)
            return payload

    async def list_assets(self) -> list[MarketAsset]:
        assets: list[MarketAsset] = []
        for page in range(1, self.settings.max_market_pages + 1):
            data = await self._get(
                "/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": self.settings.market_page_size,
                    "page": page,
                    "sparkline": "false",
                    "price_change_percentage": "1h,24h,7d",
                    "precision": "full",
                },
            )
            if not data:
                break
            for item in data:
                parsed = self._parse_asset(item)
                if parsed is not None:
                    assets.append(parsed)
            if len(data) < self.settings.market_page_size:
                break
        logger.info(
            "CoinGecko market scan completed", extra={"run_id": "provider", "count": len(assets)}
        )
        return assets

    def _parse_asset(self, item: dict[str, Any]) -> MarketAsset | None:
        try:
            symbol = str(item.get("symbol") or "").lower()
            market_cap = float(item.get("market_cap") or 0)
            volume = float(item.get("total_volume") or 0)
            price = float(item.get("current_price") or 0)
            if not symbol or symbol in self.settings.excluded_symbol_set:
                return None
            if market_cap < self.settings.min_market_cap_usd:
                return None
            if volume < self.settings.min_volume_24h_usd or price <= 0:
                return None
            updated = item.get("last_updated")
            last_updated = (
                datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if updated
                else datetime.now(UTC)
            )
            return MarketAsset(
                asset_id=str(item["id"]),
                symbol=symbol,
                name=str(item.get("name") or symbol.upper()),
                current_price=price,
                market_cap=market_cap,
                market_cap_rank=item.get("market_cap_rank"),
                volume_24h=volume,
                change_1h=float(item.get("price_change_percentage_1h_in_currency") or 0),
                change_24h=float(item.get("price_change_percentage_24h_in_currency") or 0),
                change_7d=float(item.get("price_change_percentage_7d_in_currency") or 0),
                circulating_supply=item.get("circulating_supply"),
                total_supply=item.get("total_supply"),
                ath_change_percentage=item.get("ath_change_percentage"),
                last_updated=last_updated,
            )
        except (KeyError, TypeError, ValueError):
            return None

    async def get_history(self, asset_id: str) -> MarketHistory:
        data = await self._get(
            f"/coins/{asset_id}/market_chart",
            params={"vs_currency": "usd", "days": "1", "precision": "full"},
        )
        return MarketHistory(
            asset_id=asset_id,
            prices=self._hourly_points(data.get("prices", [])),
            volumes=self._hourly_points(data.get("total_volumes", [])),
        )

    @staticmethod
    def _hourly_points(points: list[list[float | int]]) -> list[tuple[int, float]]:
        """Keep the latest sample in each UTC hour without requiring a paid interval option."""
        buckets: dict[int, tuple[int, float]] = {}
        for raw in points:
            if len(raw) < 2:
                continue
            timestamp = int(raw[0])
            value = float(raw[1])
            hour_bucket = timestamp // 3_600_000
            current = buckets.get(hour_bucket)
            if current is None or timestamp > current[0]:
                buckets[hour_bucket] = (timestamp, value)
        return [buckets[key] for key in sorted(buckets)]

    async def get_project_profile(self, asset_id: str) -> ProjectProfile:
        data = await self._get(
            f"/coins/{asset_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "false",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            },
        )
        description = str((data.get("description") or {}).get("en") or "")
        homepage = ((data.get("links") or {}).get("homepage") or [None])[0]
        fingerprint_source = "|".join(
            [asset_id, description, str(homepage), ",".join(data.get("categories") or [])]
        )
        return ProjectProfile(
            asset_id=asset_id,
            official_url=homepage or None,
            description=description[:12000],
            categories=[str(value) for value in (data.get("categories") or [])],
            genesis_date=data.get("genesis_date"),
            hashing_algorithm=data.get("hashing_algorithm"),
            source_fingerprint=hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest(),
        )

    async def get_current_price(self, asset_id: str) -> float | None:
        data = await self._get("/simple/price", params={"ids": asset_id, "vs_currencies": "usd"})
        value = (data.get(asset_id) or {}).get("usd")
        return float(value) if value is not None else None
