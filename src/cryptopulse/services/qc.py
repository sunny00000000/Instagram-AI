from __future__ import annotations

from pathlib import Path

from PIL import Image

from cryptopulse.config import Settings
from cryptopulse.providers.base import LLMProvider
from cryptopulse.schemas import ContentPackage, QCResult


class QualityController:
    def __init__(self, settings: Settings, llm: LLMProvider):
        self.settings = settings
        self.llm = llm

    async def review(self, package: ContentPackage) -> QCResult:
        checks: dict[str, bool] = {}
        errors: list[str] = []
        warnings: list[str] = []

        expected_count = self.settings.top_final_per_side
        checks["expected_unique_picks"] = (
            len(package.picks) == expected_count
            and len({pick.asset.asset_id for pick in package.picks}) == expected_count
        )
        checks["sequential_ranks"] = [pick.rank for pick in package.picks] == list(
            range(1, len(package.picks) + 1)
        )
        checks["direction_consistency"] = all(
            pick.direction == package.direction for pick in package.picks
        )
        caption_lower = package.caption.lower()
        horizon = self.settings.prediction_horizon_hours
        checks["configured_horizon"] = (
            f"{horizon} hour" in caption_lower
            or f"{horizon}-hour" in caption_lower
        )
        checks["disclaimer_present"] = "not financial advice" in caption_lower
        checks["no_prohibited_certainty"] = not any(
            phrase in caption_lower
            for phrase in ("guaranteed profit", "buy right now", "sure profit", "no risk")
        )
        checks["caption_has_all_symbols"] = all(
            pick.asset.symbol.lower() in caption_lower for pick in package.picks
        )

        carousel_assets = [asset for asset in package.assets if asset.content_type == "carousel"]
        story_assets = [asset for asset in package.assets if asset.content_type == "story"]
        checks["carousel_count"] = len(carousel_assets) == len(package.picks) + 2
        checks["story_count"] = len(story_assets) == len(package.picks) + 1
        checks["media_files_exist"] = all(Path(asset.path).is_file() for asset in package.assets)
        checks["media_dimensions"] = self._validate_dimensions(package, errors)

        for name, passed in checks.items():
            if not passed:
                errors.append(f"Deterministic QC failed: {name}")

        ai_passed, ai_errors = await self.llm.quality_review(
            {
                "direction": package.direction.value,
                "title": package.title,
                "caption": package.caption,
                "hashtags": package.hashtags,
                "picks": [pick.model_dump(mode="json") for pick in package.picks],
            }
        )
        checks["ai_content_review"] = ai_passed
        errors.extend(ai_errors)
        return QCResult(
            passed=all(checks.values()) and not errors,
            checks=checks,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _validate_dimensions(package: ContentPackage, errors: list[str]) -> bool:
        valid = True
        for asset in package.assets:
            if asset.mime_type != "image/png":
                continue
            try:
                with Image.open(asset.path) as image:
                    expected = (1080, 1350) if asset.content_type == "carousel" else (1080, 1920)
                    if image.size != expected:
                        errors.append(
                            f"Unexpected dimensions for {asset.path.name}: {image.size}, expected {expected}"
                        )
                        valid = False
            except OSError as exc:
                errors.append(f"Unable to read {asset.path}: {exc}")
                valid = False
        return valid
