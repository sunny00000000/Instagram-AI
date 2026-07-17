from __future__ import annotations

from dataclasses import dataclass

from cryptopulse.agents.workflow import (
    CleanupAgent,
    ContentStudioAgent,
    DecisionBoardAgent,
    LearningAgent,
    MarketManagerAgent,
    NewsManagerAgent,
    PublishingManagerAgent,
    QualityGateAgent,
    ResearchManagerAgent,
)
from cryptopulse.config import Settings
from cryptopulse.db import Database
from cryptopulse.orchestrator import CEOOrchestrator
from cryptopulse.providers.base import LLMProvider, MarketProvider, NewsProvider
from cryptopulse.providers.coingecko import CoinGeckoProvider
from cryptopulse.providers.llm import HeuristicLLMProvider, create_llm_provider
from cryptopulse.providers.meta import MetaPublisher
from cryptopulse.providers.mock import MockMarketProvider, MockNewsProvider
from cryptopulse.providers.news import HybridNewsProvider
from cryptopulse.services.qc import QualityController
from cryptopulse.services.repository import Repository
from cryptopulse.services.signer import MediaURLSigner


@dataclass
class Runtime:
    settings: Settings
    database: Database
    repository: Repository
    market_provider: MarketProvider
    news_provider: NewsProvider
    meta_publisher: MetaPublisher
    orchestrator: CEOOrchestrator
    signer: MediaURLSigner

    async def close(self) -> None:
        for provider in (self.market_provider, self.news_provider, self.meta_publisher):
            close = getattr(provider, "close", None)
            if close is not None:
                await close()


def create_runtime(settings: Settings, use_mock: bool = False) -> Runtime:
    settings.ensure_directories()
    database = Database(settings)
    database.create_all()
    repository = Repository(database, settings)

    if use_mock:
        market_provider: MarketProvider = MockMarketProvider()
        news_provider: NewsProvider = MockNewsProvider()
        llm: LLMProvider = HeuristicLLMProvider()
    else:
        market_provider = CoinGeckoProvider(settings)
        news_provider = HybridNewsProvider(settings)
        llm = create_llm_provider(settings)

    signer = MediaURLSigner(settings)
    meta_publisher = MetaPublisher(settings, signer)
    market_manager = MarketManagerAgent(market_provider, settings)
    news_manager = NewsManagerAgent(news_provider)
    research_manager = ResearchManagerAgent(market_provider, llm, repository, settings)
    decision_board = DecisionBoardAgent(settings)
    content_studio = ContentStudioAgent(settings, llm)
    quality_gate = QualityGateAgent(QualityController(settings, llm))
    publishing_manager = PublishingManagerAgent(meta_publisher)
    learning_agent = LearningAgent(market_provider, repository)
    cleanup_agent = CleanupAgent(settings)
    orchestrator = CEOOrchestrator(
        settings=settings,
        repository=repository,
        market_manager=market_manager,
        news_manager=news_manager,
        research_manager=research_manager,
        decision_board=decision_board,
        content_studio=content_studio,
        quality_gate=quality_gate,
        publishing_manager=publishing_manager,
        learning_agent=learning_agent,
        cleanup_agent=cleanup_agent,
    )
    return Runtime(
        settings=settings,
        database=database,
        repository=repository,
        market_provider=market_provider,
        news_provider=news_provider,
        meta_publisher=meta_publisher,
        orchestrator=orchestrator,
        signer=signer,
    )
