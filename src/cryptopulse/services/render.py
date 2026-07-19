from __future__ import annotations

import math
import textwrap
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cryptopulse.config import Settings
from cryptopulse.schemas import ContentAsset, ContentPackage, Direction, FinalPick


class MediaRenderer:
    CAROUSEL_SIZE = (1080, 1350)
    STORY_SIZE = (1080, 1920)

    def __init__(self, settings: Settings):
        self.settings = settings
        self.font_regular = self._font_path("DejaVuSans.ttf")
        self.font_bold = self._font_path("DejaVuSans-Bold.ttf")

    @staticmethod
    def _font_path(name: str) -> str:
        candidates = [
            Path("/usr/share/fonts/truetype/dejavu") / name,
            Path("/usr/share/fonts/dejavu") / name,
            Path("/Library/Fonts") / name,
            Path("C:/Windows/Fonts") / name,
        ]
        for path in candidates:
            if path.exists():
                return str(path)
        raise FileNotFoundError(f"Required system font not found: {name}")

    def render_package(self, package: ContentPackage) -> ContentPackage:
        run_dir = self.settings.media_root / package.run_id / package.direction.value
        run_dir.mkdir(parents=True, exist_ok=True)
        assets: list[ContentAsset] = []

        cover = run_dir / "carousel_00_cover.png"
        self._render_cover(cover, package.direction, package.title, self.CAROUSEL_SIZE)
        assets.append(self._asset(cover, "carousel", package.direction, *self.CAROUSEL_SIZE, 0))

        for pick in package.picks:
            path = run_dir / f"carousel_{pick.rank:02d}_{pick.asset.symbol.lower()}.png"
            self._render_pick(path, pick, self.CAROUSEL_SIZE)
            assets.append(
                self._asset(path, "carousel", package.direction, *self.CAROUSEL_SIZE, pick.rank)
            )

        disclaimer_path = run_dir / f"carousel_{len(package.picks) + 1:02d}_disclaimer.png"
        self._render_disclaimer(disclaimer_path, package.direction, self.CAROUSEL_SIZE)
        assets.append(
            self._asset(
                disclaimer_path,
                "carousel",
                package.direction,
                *self.CAROUSEL_SIZE,
                len(package.picks) + 1,
            )
        )

        story_cover = run_dir / "story_00_cover.png"
        self._render_cover(story_cover, package.direction, package.title, self.STORY_SIZE)
        assets.append(self._asset(story_cover, "story", package.direction, *self.STORY_SIZE, 0))

        for pick in package.picks:
            path = run_dir / f"story_{pick.rank:02d}_{pick.asset.symbol.lower()}.png"
            self._render_pick(path, pick, self.STORY_SIZE)
            assets.append(
                self._asset(path, "story", package.direction, *self.STORY_SIZE, pick.rank)
            )

        package.assets = assets
        return package

    @staticmethod
    def _asset(
        path: Path,
        content_type: str,
        direction: Direction,
        width: int,
        height: int,
        slide_index: int,
    ) -> ContentAsset:
        return ContentAsset(
            content_type=content_type,
            direction=direction,
            path=path,
            mime_type="image/png",
            width=width,
            height=height,
            slide_index=slide_index,
        )

    def _palette(self, direction: Direction) -> dict[str, tuple[int, int, int]]:
        if direction == Direction.BULLISH:
            return {
                "top": (10, 35, 31),
                "bottom": (7, 17, 28),
                "accent": (62, 232, 167),
                "soft": (164, 255, 221),
                "danger": (255, 190, 87),
            }
        return {
            "top": (46, 15, 25),
            "bottom": (13, 14, 27),
            "accent": (255, 91, 123),
            "soft": (255, 190, 205),
            "danger": (255, 195, 85),
        }

    def _canvas(
        self, size: tuple[int, int], direction: Direction
    ) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        width, height = size
        palette = self._palette(direction)
        image = Image.new("RGB", size)
        draw = ImageDraw.Draw(image)
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = tuple(
                round(palette["top"][channel] * (1 - ratio) + palette["bottom"][channel] * ratio)
                for channel in range(3)
            )
            draw.line((0, y, width, y), fill=color)
        for index in range(12):
            radius = 60 + index * 20
            x = width - 60 - (index % 3) * 160
            y = 90 + index * 115
            overlay = tuple(min(255, component + 15) for component in palette["top"])
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=overlay, width=2)
        return image, draw

    def _render_cover(
        self,
        path: Path,
        direction: Direction,
        title: str,
        size: tuple[int, int],
    ) -> None:
        image, draw = self._canvas(size, direction)
        width, height = size
        palette = self._palette(direction)
        badge_font = ImageFont.truetype(self.font_bold, 38 if height < 1600 else 46)
        title_font = ImageFont.truetype(self.font_bold, 82 if height < 1600 else 104)
        subtitle_font = ImageFont.truetype(self.font_regular, 36 if height < 1600 else 44)
        footer_font = ImageFont.truetype(self.font_regular, 28 if height < 1600 else 34)

        draw.rounded_rectangle((70, 90, 520, 160), radius=28, fill=palette["accent"])
        badge = "BULLISH WATCH" if direction == Direction.BULLISH else "BEARISH RISK"
        draw.text((95, 103), badge, font=badge_font, fill=(5, 12, 20))

        wrapped = self._wrap_title(title, width=18)
        y: float = 285.0 if height < 1600 else 410.0
        for line in wrapped:
            draw.text((72, y), line, font=title_font, fill=(245, 249, 255))
            y += title_font.size + 20

        draw.text(
            (75, y + 35),
            "Institutional-style public market intelligence",
            font=subtitle_font,
            fill=palette["soft"],
        )
        draw.text(
            (75, y + 95),
            f"Prediction horizon: next {self.settings.prediction_horizon_hours} hours",
            font=subtitle_font,
            fill=(218, 226, 238),
        )

        timestamp = datetime.now(UTC).strftime("Generated %d %b %Y · %H:%M UTC")
        draw.text(
            (75, height - 135), self.settings.brand_name, font=badge_font, fill=palette["accent"]
        )
        draw.text((75, height - 82), timestamp, font=footer_font, fill=(170, 183, 201))
        image.save(path, format="PNG", optimize=True)

    def _render_pick(self, path: Path, pick: FinalPick, size: tuple[int, int]) -> None:
        image, draw = self._canvas(size, pick.direction)
        width, height = size
        palette = self._palette(pick.direction)
        large = height >= 1600
        rank_font = ImageFont.truetype(self.font_bold, 96 if not large else 124)
        name_font = ImageFont.truetype(self.font_bold, 54 if not large else 66)
        symbol_font = ImageFont.truetype(self.font_bold, 42 if not large else 50)
        metric_font = ImageFont.truetype(self.font_bold, 36 if not large else 44)
        body_font = ImageFont.truetype(self.font_regular, 30 if not large else 37)
        small_font = ImageFont.truetype(self.font_regular, 24 if not large else 30)

        draw.text((68, 60), f"#{pick.rank}", font=rank_font, fill=palette["accent"])
        draw.text(
            (220, 86 if not large else 105),
            pick.asset.name[:24],
            font=name_font,
            fill=(247, 250, 255),
        )
        draw.rounded_rectangle(
            (220, 158 if not large else 190, 410, 220 if not large else 260),
            radius=22,
            fill=palette["accent"],
        )
        draw.text(
            (242, 168 if not large else 199), pick.asset.symbol, font=symbol_font, fill=(8, 13, 22)
        )

        card_top = 275 if not large else 340
        card_bottom = card_top + (235 if not large else 300)
        draw.rounded_rectangle(
            (65, card_top, width - 65, card_bottom),
            radius=36,
            fill=(14, 26, 42),
            outline=(60, 79, 102),
            width=2,
        )
        metrics = [
            (f"{self.settings.prediction_horizon_hours}H SCORE", f"{pick.final_score:.0f}/100"),
            ("CONFIDENCE", f"{pick.confidence:.0f}%"),
            ("RISK", pick.risk_level.value.upper()),
            ("1H", f"{pick.asset.change_1h:+.2f}%"),
        ]
        cell_width = (width - 130) / 4
        for index, (label, value) in enumerate(metrics):
            x = 82 + index * cell_width
            draw.text((x, card_top + 38), label, font=small_font, fill=(159, 174, 195))
            value_color = palette["accent"] if label != "RISK" else palette["danger"]
            draw.text((x, card_top + 92), value, font=metric_font, fill=value_color)

        chart_top = card_bottom + 55
        chart_bottom = chart_top + (210 if not large else 300)
        draw.rounded_rectangle(
            (65, chart_top, width - 65, chart_bottom),
            radius=28,
            fill=(10, 20, 34),
            outline=(52, 69, 92),
            width=2,
        )
        draw.text((90, chart_top + 26), "PUBLIC PRICE TREND", font=small_font, fill=(166, 182, 203))
        self._draw_sparkline(
            draw,
            pick.sparkline,
            (95, chart_top + 82, width - 95, chart_bottom - 40),
            palette["accent"],
        )

        text_top = chart_bottom + 50
        draw.text((68, text_top), "WHY IT RANKED", font=metric_font, fill=palette["accent"])
        y = float(text_top + 58)
        for line in textwrap.wrap(pick.thesis, width=54 if not large else 46)[:5]:
            draw.text((70, y), line, font=body_font, fill=(228, 235, 245))
            y += body_font.size + 9

        invalidation_top = min(height - 235, y + 26)
        draw.text((68, invalidation_top), "INVALIDATION", font=small_font, fill=palette["danger"])
        y = float(invalidation_top + 42)
        for line in textwrap.wrap(pick.invalidation, width=66 if not large else 54)[:3]:
            draw.text((70, y), line, font=small_font, fill=(194, 205, 220))
            y += small_font.size + 7

        draw.text(
            (68, height - 74), self.settings.brand_handle, font=small_font, fill=(146, 161, 182)
        )
        draw.text(
            (width - 360, height - 74),
            "Not financial advice",
            font=small_font,
            fill=(146, 161, 182),
        )
        image.save(path, format="PNG", optimize=True)

    def _render_disclaimer(self, path: Path, direction: Direction, size: tuple[int, int]) -> None:
        image, draw = self._canvas(size, direction)
        width, height = size
        palette = self._palette(direction)
        title_font = ImageFont.truetype(self.font_bold, 72 if height < 1600 else 88)
        body_font = ImageFont.truetype(self.font_regular, 35 if height < 1600 else 42)
        small_font = ImageFont.truetype(self.font_regular, 26 if height < 1600 else 32)
        draw.text((70, 110), "READ BEFORE YOU ACT", font=title_font, fill=palette["accent"])
        paragraphs = [
            self.settings.disclaimer,
            "Rankings use public market, news, project and liquidity signals available at generation time. They can become invalid within minutes.",
            "A bullish watch is not a buy instruction. A bearish risk is not a sell instruction. Verify sources and manage your own risk.",
            "Prediction window: six hours from the timestamp on the cover.",
        ]
        y: float = 310.0 if height < 1600 else 420.0
        for paragraph in paragraphs:
            draw.rounded_rectangle(
                (65, y - 25, width - 65, y + 180),
                radius=26,
                fill=(12, 24, 40),
                outline=(56, 73, 96),
                width=2,
            )
            for line in textwrap.wrap(paragraph, width=54 if height < 1600 else 46):
                draw.text((95, y), line, font=body_font, fill=(230, 237, 246))
                y += body_font.size + 10
            y += 80
        draw.text(
            (70, height - 115), self.settings.brand_name, font=body_font, fill=palette["accent"]
        )
        draw.text(
            (70, height - 65),
            "Public data · Transparent uncertainty · No guaranteed outcomes",
            font=small_font,
            fill=(166, 180, 200),
        )
        image.save(path, format="PNG", optimize=True)

    @staticmethod
    def _draw_sparkline(
        draw: ImageDraw.ImageDraw,
        values: list[float],
        bounds: tuple[float, float, float, float],
        color: tuple[int, int, int],
    ) -> None:
        left, top, right, bottom = bounds
        if len(values) < 2:
            draw.line(
                (left, (top + bottom) / 2, right, (top + bottom) / 2), fill=(100, 115, 135), width=4
            )
            return
        minimum, maximum = min(values), max(values)
        span = max(maximum - minimum, 1e-9)
        points = []
        for index, value in enumerate(values):
            x = left + (right - left) * index / (len(values) - 1)
            y = bottom - (bottom - top) * (value - minimum) / span
            points.append((x, y))
        draw.line(points, fill=color, width=7, joint="curve")
        for x, y in points[:: max(1, math.ceil(len(points) / 6))]:
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color)

    @staticmethod
    def _wrap_title(title: str, width: int) -> list[str]:
        upper = title.upper().strip()
        if ": " in upper:
            heading, detail = upper.split(": ", maxsplit=1)
            return [*textwrap.wrap(heading, width=width), *textwrap.wrap(detail, width=width)][:4]
        return textwrap.wrap(upper, width=width)[:4]
