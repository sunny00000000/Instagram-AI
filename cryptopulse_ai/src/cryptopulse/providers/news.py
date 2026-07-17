from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from cryptopulse.config import Settings
from cryptopulse.providers.base import NewsProvider
from cryptopulse.schemas import NewsItem

logger = logging.getLogger(__name__)


class HybridNewsProvider(NewsProvider):
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={"user-agent": "CryptoPulseAI/0.1"},
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def fetch_news(self) -> list[NewsItem]:
        tasks = [self._fetch_rss(url) for url in self.settings.rss_feed_list]
        tasks.append(self._fetch_gdelt())
        results = await asyncio.gather(*tasks, return_exceptions=True)
        deduped: dict[str, NewsItem] = {}
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("News source failed: %s", result, extra={"run_id": "provider"})
                continue
            for item in result:
                key = str(item.url).split("?")[0].lower()
                deduped[key] = item
        items = sorted(deduped.values(), key=lambda item: item.published_at, reverse=True)
        logger.info("News scan completed", extra={"run_id": "provider", "count": len(items)})
        return items

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,
    )
    async def _fetch_rss(self, url: str) -> list[NewsItem]:
        response = await self.client.get(url)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        source = parsed.feed.get("title") or url
        output: list[NewsItem] = []
        for entry in parsed.entries[:75]:
            published = self._parse_date(entry.get("published") or entry.get("updated"))
            output.append(
                NewsItem(
                    title=str(entry.get("title") or "Untitled"),
                    summary=self._clean_summary(str(entry.get("summary") or ""))[:1500],
                    url=str(entry.get("link") or url),
                    source=str(source),
                    published_at=published,
                )
            )
        return output

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, ValueError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,
    )
    async def _fetch_gdelt(self) -> list[NewsItem]:
        query = '(cryptocurrency OR bitcoin OR ethereum OR blockchain OR "digital asset")'
        response = await self.client.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params={
                "query": query,
                "mode": "ArtList",
                "format": "json",
                "maxrecords": self.settings.gdelt_max_records,
                "sort": "HybridRel",
                "timespan": "12h",
            },
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        output: list[NewsItem] = []
        for article in data.get("articles", []):
            output.append(
                NewsItem(
                    title=str(article.get("title") or "Untitled"),
                    summary="",
                    url=str(article.get("url") or "https://www.gdeltproject.org/"),
                    source=str(article.get("domain") or "GDELT"),
                    published_at=self._parse_gdelt_date(article.get("seendate")),
                    categories=["global_news"],
                )
            )
        return output

    @staticmethod
    def _parse_date(value: str | None) -> datetime:
        if not value:
            return datetime.now(UTC)
        try:
            parsed = parsedate_to_datetime(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            return datetime.now(UTC)

    @staticmethod
    def _parse_gdelt_date(value: str | None) -> datetime:
        if not value:
            return datetime.now(UTC)
        for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=UTC)
            except ValueError:
                pass
        return datetime.now(UTC)

    @staticmethod
    def _clean_summary(value: str) -> str:
        in_tag = False
        output: list[str] = []
        for char in value:
            if char == "<":
                in_tag = True
                continue
            if char == ">":
                in_tag = False
                continue
            if not in_tag:
                output.append(char)
        return " ".join("".join(output).split())
