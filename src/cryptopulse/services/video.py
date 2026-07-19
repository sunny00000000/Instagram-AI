from __future__ import annotations

import logging
import shutil
import subprocess

from cryptopulse.schemas import ContentAsset, ContentPackage

logger = logging.getLogger(__name__)


class ReelBuilder:
    def build(self, package: ContentPackage) -> ContentPackage:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            logger.warning(
                "ffmpeg not available; Reel generation skipped", extra={"run_id": package.run_id}
            )
            return package
        story_assets = sorted(
            [asset for asset in package.assets if asset.content_type == "story"],
            key=lambda asset: asset.slide_index or 0,
        )
        if not story_assets:
            return package
        output = story_assets[0].path.parent / "reel.mp4"
        list_file = story_assets[0].path.parent / "reel_inputs.txt"
        lines: list[str] = []
        for asset in story_assets:
            escaped = str(asset.path.resolve()).replace("'", "'\\''")
            lines.extend([f"file '{escaped}'", "duration 2.4"])
        lines.append(f"file '{str(story_assets[-1].path.resolve()).replace("'", "'\\''")}'")
        list_file.write_text("\n".join(lines), encoding="utf-8")
        command = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-vf",
            "format=yuv420p,scale=1080:1920",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-movflags",
            "+faststart",
            str(output),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)
            package.assets.append(
                ContentAsset(
                    content_type="reel",
                    direction=package.direction,
                    path=output,
                    mime_type="video/mp4",
                    width=1080,
                    height=1920,
                )
            )
        except (subprocess.SubprocessError, OSError) as exc:
            logger.error("Reel generation failed: %s", exc, extra={"run_id": package.run_id})
        finally:
            list_file.unlink(missing_ok=True)
        return package
