from cryptopulse.providers.llm import HeuristicLLMProvider
from cryptopulse.providers.mock import MockMarketProvider
from cryptopulse.schemas import Direction
from cryptopulse.services.scoring import create_preliminary_signals, select_final_picks


async def test_preliminary_and_final_ranking():
    provider = MockMarketProvider(count=60)
    assets = await provider.list_assets()
    bullish, bearish = create_preliminary_signals(assets, per_side=15)
    assert len(bullish) == 15
    assert len(bearish) == 15
    assert all(item.direction == Direction.BULLISH for item in bullish)
    assert all(item.direction == Direction.BEARISH for item in bearish)
    assert not (
        {item.asset.asset_id for item in bullish} & {item.asset.asset_id for item in bearish}
    )

    llm = HeuristicLLMProvider()
    profiles = {
        item.asset.asset_id: await provider.get_project_profile(item.asset.asset_id)
        for item in bullish
    }
    analyses = await llm.analyze_batch(
        [item.asset for item in bullish], [], profiles, Direction.BULLISH
    )
    histories = {
        item.asset.asset_id: await provider.get_history(item.asset.asset_id) for item in bullish
    }
    final = select_final_picks(bullish, analyses, histories, final_count=5)
    assert len(final) == 5
    assert [pick.rank for pick in final] == [1, 2, 3, 4, 5]
    assert all(0 <= pick.final_score <= 100 for pick in final)
