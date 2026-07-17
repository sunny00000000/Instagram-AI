from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from cryptopulse.config import Settings
from cryptopulse.schemas import ContentAsset, ContentPackage, PublishRecord
from cryptopulse.services.signer import MediaURLSigner

logger = logging.getLogger(__name__)


class MetaPublisher:
    def __init__(self, settings: Settings, signer: MediaURLSigner):
        self.settings = settings
        self.signer = signer
        self.base_url = f"https://graph.facebook.com/{settings.meta_graph_version}"
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(90.0))

    async def close(self) -> None:
        await self.client.aclose()

    async def publish(self, package: ContentPackage) -> list[PublishRecord]:
        if self.settings.dry_run:
            return self._dry_run_records(package)
        records: list[PublishRecord] = []
        if self.settings.publish_instagram:
            records.append(await self._publish_instagram_carousel(package))
            if self.settings.publish_stories:
                records.extend(await self._publish_instagram_stories(package))
            if self.settings.publish_reels:
                reel = next(
                    (asset for asset in package.assets if asset.content_type == "reel"), None
                )
                if reel:
                    records.append(await self._publish_instagram_reel(package, reel))
        if self.settings.publish_facebook:
            records.append(await self._publish_facebook_album(package))
        return records

    def _dry_run_records(self, package: ContentPackage) -> list[PublishRecord]:
        records = [
            PublishRecord(
                platform="instagram",
                content_type="carousel",
                direction=package.direction,
                success=True,
                external_id=f"dry-run-ig-carousel-{package.run_id}-{package.direction.value}",
                published_at=datetime.now(UTC),
            ),
            PublishRecord(
                platform="facebook",
                content_type="album",
                direction=package.direction,
                success=True,
                external_id=f"dry-run-fb-album-{package.run_id}-{package.direction.value}",
                published_at=datetime.now(UTC),
            ),
        ]
        return records

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=2, max=40),
        reraise=True,
    )
    async def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        payload = {**data, "access_token": self.settings.meta_access_token}
        response = await self.client.post(f"{self.base_url}/{path.lstrip('/')}", data=payload)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        if "error" in result:
            raise RuntimeError(str(result["error"]))
        return result

    async def _publish_instagram_carousel(self, package: ContentPackage) -> PublishRecord:
        try:
            carousel_assets = sorted(
                [asset for asset in package.assets if asset.content_type == "carousel"],
                key=lambda asset: asset.slide_index or 0,
            )
            child_ids: list[str] = []
            for asset in carousel_assets:
                result = await self._post(
                    f"{self.settings.instagram_user_id}/media",
                    {
                        "image_url": self._public_url(asset.path),
                        "is_carousel_item": "true",
                    },
                )
                child_ids.append(str(result["id"]))
            container = await self._post(
                f"{self.settings.instagram_user_id}/media",
                {
                    "media_type": "CAROUSEL",
                    "children": ",".join(child_ids),
                    "caption": self._caption(package),
                },
            )
            creation_id = str(container["id"])
            await self._wait_for_container(creation_id)
            published = await self._post(
                f"{self.settings.instagram_user_id}/media_publish",
                {"creation_id": creation_id},
            )
            return self._record("instagram", "carousel", package, True, str(published["id"]))
        except Exception as exc:
            logger.exception("Instagram carousel publish failed", extra={"run_id": package.run_id})
            return self._record("instagram", "carousel", package, False, error=str(exc))

    async def _publish_instagram_stories(self, package: ContentPackage) -> list[PublishRecord]:
        records: list[PublishRecord] = []
        assets = sorted(
            [asset for asset in package.assets if asset.content_type == "story"],
            key=lambda asset: asset.slide_index or 0,
        )
        for asset in assets:
            try:
                container = await self._post(
                    f"{self.settings.instagram_user_id}/media",
                    {"image_url": self._public_url(asset.path), "media_type": "STORIES"},
                )
                creation_id = str(container["id"])
                await self._wait_for_container(creation_id)
                published = await self._post(
                    f"{self.settings.instagram_user_id}/media_publish",
                    {"creation_id": creation_id},
                )
                records.append(
                    self._record("instagram", "story", package, True, str(published["id"]))
                )
            except Exception as exc:
                records.append(self._record("instagram", "story", package, False, error=str(exc)))
                break
        return records

    async def _publish_instagram_reel(
        self, package: ContentPackage, asset: ContentAsset
    ) -> PublishRecord:
        try:
            container = await self._post(
                f"{self.settings.instagram_user_id}/media",
                {
                    "video_url": self._public_url(asset.path),
                    "media_type": "REELS",
                    "caption": self._caption(package),
                    "share_to_feed": "true",
                },
            )
            creation_id = str(container["id"])
            await self._wait_for_container(creation_id, attempts=30)
            published = await self._post(
                f"{self.settings.instagram_user_id}/media_publish",
                {"creation_id": creation_id},
            )
            return self._record("instagram", "reel", package, True, str(published["id"]))
        except Exception as exc:
            return self._record("instagram", "reel", package, False, error=str(exc))

    async def _publish_facebook_album(self, package: ContentPackage) -> PublishRecord:
        try:
            assets = sorted(
                [asset for asset in package.assets if asset.content_type == "carousel"],
                key=lambda asset: asset.slide_index or 0,
            )
            attached: list[dict[str, str]] = []
            for asset in assets:
                result = await self._post(
                    f"{self.settings.facebook_page_id}/photos",
                    {"url": self._public_url(asset.path), "published": "false"},
                )
                attached.append({"media_fbid": str(result["id"])})
            published = await self._post(
                f"{self.settings.facebook_page_id}/feed",
                {
                    "message": self._caption(package),
                    "attached_media": json.dumps(attached),
                },
            )
            return self._record("facebook", "album", package, True, str(published["id"]))
        except Exception as exc:
            logger.exception("Facebook album publish failed", extra={"run_id": package.run_id})
            return self._record("facebook", "album", package, False, error=str(exc))

    async def _wait_for_container(self, creation_id: str, attempts: int = 15) -> None:
        for _ in range(attempts):
            response = await self.client.get(
                f"{self.base_url}/{creation_id}",
                params={
                    "fields": "status_code,status",
                    "access_token": self.settings.meta_access_token,
                },
            )
            response.raise_for_status()
            data = response.json()
            status = str(data.get("status_code") or "").upper()
            if status == "FINISHED":
                return
            if status in {"ERROR", "EXPIRED"}:
                raise RuntimeError(f"Meta container {creation_id} entered {status}: {data}")
            await asyncio.sleep(5)
        raise TimeoutError(f"Meta container {creation_id} did not finish processing")

    def _public_url(self, path: Path) -> str:
        relative = path.relative_to(self.settings.media_root).as_posix()
        return self.signer.sign_path(relative)

    @staticmethod
    def _caption(package: ContentPackage) -> str:
        hashtags = " ".join(f"#{tag.lstrip('#')}" for tag in package.hashtags)
        return f"{package.caption}\n\n{hashtags}".strip()

    @staticmethod
    def _record(
        platform: str,
        content_type: str,
        package: ContentPackage,
        success: bool,
        external_id: str | None = None,
        error: str | None = None,
    ) -> PublishRecord:
        return PublishRecord(
            platform=platform,
            content_type=content_type,
            direction=package.direction,
            success=success,
            external_id=external_id,
            error=error,
            published_at=datetime.now(UTC) if success else None,
        )
