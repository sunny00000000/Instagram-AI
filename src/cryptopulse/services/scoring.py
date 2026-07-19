from __future__ import annotations

import math
import statistics
from collections.abc import Iterable

from cryptopulse.schemas import (
    DeepAnalysis,
    Direction,
    FinalPick,
    MarketAsset,
    MarketHistory,
    PreliminarySignal,
    RiskLevel,
)


def _z_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    mean = statistics.fmean(values)
    std = statistics.pstdev(values)
    if std < 1e-9:
        return [0.0 for _ in values]
    return [(value - mean) / std for value in values]


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def create_preliminary_signals(
    assets: list[MarketAsset],
    per_side: int,
) -> tuple[list[PreliminarySignal], list[PreliminarySignal]]:
    if not assets:
        return [], []
    z_1h = _z_scores([asset.change_1h for asset in assets])
    z_24h = _z_scores([asset.change_24h for asset in assets])
    z_7d = _z_scores([asset.change_7d for asset in assets])
    z_liquidity = _z_scores([math.log10(max(asset.liquidity_ratio, 1e-9)) for asset in assets])
    z_market_cap = _z_scores([math.log10(max(asset.market_cap, 1)) for asset in assets])
    z_volatility = _z_scores(
        [
            abs(asset.change_1h) + abs(asset.change_24h) / 4 + abs(asset.change_7d) / 14
            for asset in assets
        ]
    )

    bullish: list[PreliminarySignal] = []
    bearish: list[PreliminarySignal] = []
    for index, asset in enumerate(assets):
        directional = 0.50 * z_1h[index] + 0.32 * z_24h[index] + 0.18 * z_7d[index]
        liquidity = 0.70 * z_liquidity[index] + 0.30 * z_market_cap[index]
        quality_adjustment = 5.0 * liquidity - 3.0 * max(0.0, z_volatility[index] - 2.0)
        bullish_score = _clamp(50 + directional * 15 + quality_adjustment)
        bearish_score = _clamp(50 - directional * 15 + quality_adjustment)

        reasons = [
            f"1h change {asset.change_1h:+.2f}%",
            f"24h change {asset.change_24h:+.2f}%",
            f"24h volume ${asset.volume_24h:,.0f}",
        ]
        bullish.append(
            PreliminarySignal(
                asset=asset,
                direction=Direction.BULLISH,
                preliminary_score=bullish_score,
                liquidity_score=_clamp(50 + liquidity * 12),
                momentum_score=_clamp(50 + directional * 15),
                volatility_score=_clamp(50 + z_volatility[index] * 12),
                reasons=reasons,
            )
        )
        bearish.append(
            PreliminarySignal(
                asset=asset,
                direction=Direction.BEARISH,
                preliminary_score=bearish_score,
                liquidity_score=_clamp(50 + liquidity * 12),
                momentum_score=_clamp(50 - directional * 15),
                volatility_score=_clamp(50 + z_volatility[index] * 12),
                reasons=reasons,
            )
        )

    bullish.sort(key=lambda item: (item.preliminary_score, item.asset.volume_24h), reverse=True)
    bearish.sort(key=lambda item: (item.preliminary_score, item.asset.volume_24h), reverse=True)
    bullish = _dedupe_family(bullish)[:per_side]
    bearish = _dedupe_family(bearish)[:per_side]
    bearish_ids = {item.asset.asset_id for item in bullish}
    bearish = [item for item in bearish if item.asset.asset_id not in bearish_ids][:per_side]
    return bullish, bearish


def _dedupe_family(signals: Iterable[PreliminarySignal]) -> list[PreliminarySignal]:
    """Avoid accidental symbol duplicates from wrapped or bridged listings."""
    output: list[PreliminarySignal] = []
    seen: set[str] = set()
    for signal in signals:
        key = signal.asset.symbol.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(signal)
    return output


def compute_rsi(history: MarketHistory, period: int = 14) -> float:
    prices = [value for _, value in history.prices]
    if len(prices) <= period:
        return 50.0
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(prices[-period - 1 : -1], prices[-period:], strict=False):
        delta = current - previous
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    average_gain = statistics.fmean(gains) if gains else 0
    average_loss = statistics.fmean(losses) if losses else 0
    if average_loss <= 1e-12:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def history_slope(history: MarketHistory) -> float:
    prices = [value for _, value in history.prices]
    if len(prices) < 2 or prices[0] == 0:
        return 0.0
    return ((prices[-1] - prices[0]) / prices[0]) * 100


def select_final_picks(
    preliminaries: list[PreliminarySignal],
    analyses: list[DeepAnalysis],
    histories: dict[str, MarketHistory],
    final_count: int,
) -> list[FinalPick]:
    analysis_by_id = {analysis.asset_id: analysis for analysis in analyses}
    ranked: list[tuple[float, PreliminarySignal, DeepAnalysis]] = []
    for preliminary in preliminaries:
        analysis = analysis_by_id.get(preliminary.asset.asset_id)
        if analysis is None:
            continue
        history = histories.get(
            preliminary.asset.asset_id, MarketHistory(asset_id=preliminary.asset.asset_id)
        )
        rsi = compute_rsi(history)
        slope = history_slope(history)
        direction_factor = 1 if preliminary.direction == Direction.BULLISH else -1
        technical_confirmation = _clamp(50 + direction_factor * slope * 3)
        if preliminary.direction == Direction.BULLISH and rsi > 82:
            technical_confirmation -= 8
        if preliminary.direction == Direction.BEARISH and rsi < 18:
            technical_confirmation -= 8
        final_score = (
            preliminary.preliminary_score * 0.25
            + analysis.technical_score * 0.25
            + analysis.news_score * 0.15
            + analysis.fundamental_score * 0.10
            + analysis.public_intelligence_score * 0.10
            + technical_confirmation * 0.15
            - analysis.contradiction_score * 0.18
        )
        ranked.append((_clamp(final_score), preliminary, analysis))

    ranked.sort(key=lambda item: (item[0], item[2].confidence), reverse=True)
    picks: list[FinalPick] = []
    for rank, (score, preliminary, analysis) in enumerate(ranked[:final_count], start=1):
        pick_history = histories.get(preliminary.asset.asset_id)
        sparkline = [price for _, price in pick_history.prices[-18:]] if pick_history else []
        picks.append(
            FinalPick(
                rank=rank,
                asset=preliminary.asset,
                direction=preliminary.direction,
                final_score=score,
                confidence=analysis.confidence,
                risk_level=analysis.risk_level or RiskLevel.HIGH,
                thesis=analysis.thesis,
                invalidation=analysis.invalidation,
                evidence=analysis.evidence,
                source_urls=analysis.source_urls,
                sparkline=sparkline,
            )
        )
    return picks
