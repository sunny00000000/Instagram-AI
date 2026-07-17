from __future__ import annotations

from abc import ABC, abstractmethod

from cryptopulse.schemas import (
    DeepAnalysis,
    Direction,
    MarketAsset,
    MarketHistory,
    NewsItem,
    ProjectProfile,
)


class MarketProvider(ABC):
    @abstractmethod
    async def list_assets(self) -> list[MarketAsset]:
        raise NotImplementedError

    @abstractmethod
    async def get_history(self, asset_id: str) -> MarketHistory:
        raise NotImplementedError

    @abstractmethod
    async def get_project_profile(self, asset_id: str) -> ProjectProfile:
        raise NotImplementedError

    @abstractmethod
    async def get_current_price(self, asset_id: str) -> float | None:
        raise NotImplementedError


class NewsProvider(ABC):
    @abstractmethod
    async def fetch_news(self) -> list[NewsItem]:
        raise NotImplementedError


class LLMProvider(ABC):
    @abstractmethod
    async def analyze_batch(
        self,
        assets: list[MarketAsset],
        news: list[NewsItem],
        profiles: dict[str, ProjectProfile],
        direction: Direction,
    ) -> list[DeepAnalysis]:
        raise NotImplementedError

    @abstractmethod
    async def improve_caption(self, caption: str, direction: Direction) -> str:
        raise NotImplementedError

    @abstractmethod
    async def quality_review(self, payload: dict) -> tuple[bool, list[str]]:
        raise NotImplementedError
