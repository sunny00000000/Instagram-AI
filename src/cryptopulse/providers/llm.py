from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, cast

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from cryptopulse.config import Settings
from cryptopulse.providers.base import LLMProvider
from cryptopulse.schemas import (
    DeepAnalysis,
    Direction,
    MarketAsset,
    NewsItem,
    ProjectProfile,
    RiskLevel,
)

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start_candidates = [pos for pos in (cleaned.find("["), cleaned.find("{")) if pos >= 0]
        if not start_candidates:
            raise
        start = min(start_candidates)
        end = max(cleaned.rfind("]"), cleaned.rfind("}"))
        if end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


class GeminiLLMProvider(LLMProvider):
    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for LLM_PROVIDER=gemini")
        self.settings = settings
        from google import genai

        self.client = genai.Client(api_key=settings.gemini_api_key)
        self._semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30),
        reraise=True,
    )
    async def _complete(self, prompt: str) -> str:
        async with self._semaphore:
            interaction = await asyncio.to_thread(
                self.client.interactions.create,
                model=self.settings.gemini_model,
                input=prompt,
            )
            return str(cast(Any, interaction).output_text)

    async def analyze_batch(
        self,
        assets: list[MarketAsset],
        news: list[NewsItem],
        profiles: dict[str, ProjectProfile],
        direction: Direction,
    ) -> list[DeepAnalysis]:
        prompt = build_analysis_prompt(assets, news, profiles, direction)
        raw = await self._complete(prompt)
        return parse_analysis_response(raw, assets, direction)

    async def improve_caption(self, caption: str, direction: Direction) -> str:
        prompt = f"""
Rewrite the social caption below for a global Instagram/Facebook audience.
Keep every number, ranking, ticker, time horizon, disclaimer and source claim unchanged.
Use evidence-based language only. Never say guaranteed, buy now, sell now, sure profit or no risk.
Direction: {direction.value}
Return only the improved caption.

CAPTION:
{caption}
""".strip()
        result = await self._complete(prompt)
        return result.strip() or caption

    async def quality_review(self, payload: dict) -> tuple[bool, list[str]]:
        prompt = f"""
You are an independent financial-content quality reviewer.
Review the JSON below for contradictions, unsupported certainty, incorrect direction language,
missing six-hour horizon, missing disclaimer, ranking inconsistencies, or misleading claims.
Return only JSON: {{"passed": true|false, "errors": ["..."]}}.

{json.dumps(payload, ensure_ascii=False, default=str)}
""".strip()
        data = _extract_json(await self._complete(prompt))
        return bool(data.get("passed")), [str(item) for item in data.get("errors", [])]


class OpenAILLMProvider(LLMProvider):
    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for LLM_PROVIDER=openai")
        self.settings = settings
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds
        )
        self._semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30),
        reraise=True,
    )
    async def _complete(self, prompt: str) -> str:
        async with self._semaphore:
            response = await self.client.responses.create(
                model=self.settings.openai_model, input=prompt
            )
            return str(response.output_text)

    async def analyze_batch(
        self,
        assets: list[MarketAsset],
        news: list[NewsItem],
        profiles: dict[str, ProjectProfile],
        direction: Direction,
    ) -> list[DeepAnalysis]:
        raw = await self._complete(build_analysis_prompt(assets, news, profiles, direction))
        return parse_analysis_response(raw, assets, direction)

    async def improve_caption(self, caption: str, direction: Direction) -> str:
        raw = await self._complete(
            "Rewrite this evidence-based social caption without changing factual values, rankings, "
            "tickers, six-hour horizon or disclaimer. Return only the caption.\n\n" + caption
        )
        return raw.strip() or caption

    async def quality_review(self, payload: dict) -> tuple[bool, list[str]]:
        raw = await self._complete(
            "Review this financial-content JSON. Return only JSON with passed boolean and errors list. "
            "Reject guaranteed language, missing six-hour horizon, contradictions or unsupported claims.\n"
            + json.dumps(payload, ensure_ascii=False, default=str)
        )
        data = _extract_json(raw)
        return bool(data.get("passed")), [str(item) for item in data.get("errors", [])]


class HeuristicLLMProvider(LLMProvider):
    """Deterministic fallback used for tests and zero-key dry runs."""

    async def analyze_batch(
        self,
        assets: list[MarketAsset],
        news: list[NewsItem],
        profiles: dict[str, ProjectProfile],
        direction: Direction,
    ) -> list[DeepAnalysis]:
        output: list[DeepAnalysis] = []
        for asset in assets:
            matching = match_news(asset, news)
            news_text = " ".join(f"{item.title} {item.summary}" for item in matching).lower()
            positive = sum(
                news_text.count(word)
                for word in ("approval", "launch", "partnership", "growth", "upgrade")
            )
            negative = sum(
                news_text.count(word)
                for word in ("hack", "lawsuit", "ban", "exploit", "outage", "delist")
            )
            directional = asset.change_1h * 2.5 + asset.change_24h * 0.8 + asset.change_7d * 0.15
            if direction == Direction.BEARISH:
                directional *= -1
            technical = max(0.0, min(100.0, 50 + directional * 2))
            news_score = max(
                0.0,
                min(
                    100.0,
                    50 + (positive - negative) * 7 * (1 if direction == Direction.BULLISH else -1),
                ),
            )
            profile = profiles.get(asset.asset_id)
            fundamental = 62.0 if profile and profile.description else 45.0
            public_score = max(0.0, min(100.0, 50 + asset.liquidity_ratio * 100))
            contradiction = max(0.0, min(100.0, 100 - (technical + news_score) / 2))
            confidence = max(
                35.0,
                min(
                    90.0,
                    technical * 0.45
                    + news_score * 0.25
                    + fundamental * 0.15
                    + public_score * 0.15
                    - contradiction * 0.2,
                ),
            )
            risk = (
                RiskLevel.EXTREME
                if asset.market_cap < 20_000_000
                else RiskLevel.HIGH
                if asset.market_cap < 100_000_000
                else RiskLevel.MEDIUM
            )
            thesis = (
                f"{asset.name} shows {'positive' if direction == Direction.BULLISH else 'negative'} "
                f"short-horizon momentum with {asset.change_1h:+.2f}% over one hour and "
                f"{asset.change_24h:+.2f}% over 24 hours."
            )
            invalidation = (
                "Momentum reverses with declining volume and loss of the current six-hour trend."
            )
            output.append(
                DeepAnalysis(
                    asset_id=asset.asset_id,
                    direction=direction,
                    technical_score=technical,
                    news_score=news_score,
                    fundamental_score=fundamental,
                    public_intelligence_score=public_score,
                    contradiction_score=contradiction,
                    confidence=confidence,
                    risk_level=risk,
                    thesis=thesis,
                    invalidation=invalidation,
                    evidence=[item.title for item in matching[:3]]
                    or ["Market-price and liquidity signals"],
                    source_urls=[str(item.url) for item in matching[:3]],
                )
            )
        return output

    async def improve_caption(self, caption: str, direction: Direction) -> str:
        return caption

    async def quality_review(self, payload: dict) -> tuple[bool, list[str]]:
        text = json.dumps(payload).lower()
        prohibited = ["guaranteed profit", "buy right now", "sure profit", "no risk"]
        errors = [f"Prohibited phrase: {phrase}" for phrase in prohibited if phrase in text]
        return not errors, errors


def match_news(asset: MarketAsset, news: list[NewsItem]) -> list[NewsItem]:
    terms = {asset.name.lower(), asset.symbol.lower(), asset.asset_id.lower()}
    output: list[NewsItem] = []
    for item in news:
        haystack = f"{item.title} {item.summary}".lower()
        if any(term and re.search(rf"\b{re.escape(term)}\b", haystack) for term in terms):
            output.append(item)
    return output


def build_analysis_prompt(
    assets: list[MarketAsset],
    news: list[NewsItem],
    profiles: dict[str, ProjectProfile],
    direction: Direction,
) -> str:
    asset_payload: list[dict[str, Any]] = []
    for asset in assets:
        related_news = match_news(asset, news)[:8]
        profile = profiles.get(asset.asset_id)
        asset_payload.append(
            {
                "asset": asset.model_dump(mode="json"),
                "project_profile": profile.model_dump(mode="json") if profile else None,
                "related_news": [item.model_dump(mode="json") for item in related_news],
            }
        )
    return f"""
You are a multi-disciplinary crypto market decision board. Analyze only the supplied public data.
Prediction horizon: six hours. Direction under review: {direction.value}.
Do not invent prices, events, partnerships, wallet activity, whitepaper facts, or sources.
Use probabilities, not certainty. Treat thin liquidity, missing news, conflicting signals and low market cap as higher risk.

Return only a JSON array. One object per asset with exactly these keys:
asset_id, direction, technical_score, news_score, fundamental_score,
public_intelligence_score, contradiction_score, confidence, risk_level,
thesis, invalidation, evidence, source_urls.
Scores are 0-100. risk_level is low, medium, high or extreme.
direction must be {direction.value}. thesis and invalidation must be concise.

INPUT:
{json.dumps(asset_payload, ensure_ascii=False, default=str)}
""".strip()


def parse_analysis_response(
    raw: str,
    assets: list[MarketAsset],
    direction: Direction,
) -> list[DeepAnalysis]:
    data = _extract_json(raw)
    if isinstance(data, dict):
        data = data.get("analyses") or data.get("results") or [data]
    known_ids = {asset.asset_id for asset in assets}
    output: list[DeepAnalysis] = []
    for item in data:
        if item.get("asset_id") not in known_ids:
            continue
        item["direction"] = direction.value
        try:
            output.append(DeepAnalysis.model_validate(item))
        except Exception as exc:
            logger.warning("Discarding invalid LLM analysis: %s", exc, extra={"run_id": "llm"})
    return output


def create_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.lower().strip()
    if provider == "gemini":
        if not settings.gemini_api_key:
            logger.warning(
                "No Gemini key configured; falling back to heuristic analysis",
                extra={"run_id": "system"},
            )
            return HeuristicLLMProvider()
        return GeminiLLMProvider(settings)
    if provider == "openai":
        if not settings.openai_api_key:
            logger.warning(
                "No OpenAI key configured; falling back to heuristic analysis",
                extra={"run_id": "system"},
            )
            return HeuristicLLMProvider()
        return OpenAILLMProvider(settings)
    return HeuristicLLMProvider()
