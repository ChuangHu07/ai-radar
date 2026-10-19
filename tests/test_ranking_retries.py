import asyncio
import httpx
from app.sources.rankings import RankingService
from test_rankings import chart


def test_three_auto_failures_persist_and_manual_fetch_can_recover(tmp_path):
    count=0
    healthy=False
    def respond(request):
        nonlocal count
        count+=1
        return httpx.Response(200,text=chart()) if healthy else httpx.Response(503)
    async def run():
        nonlocal healthy
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            service=RankingService(tmp_path,client)
            for _ in range(3):await service.fetch('auto')
            before=count
            restarted=RankingService(tmp_path,client)
            assert restarted.state()['stopped'] and restarted.state()['auto_attempts']==3
            await restarted.fetch('auto')
            assert count==before
            healthy=True
            value=await restarted.fetch('manual')
            assert value['source_state']=='live' and value['error'] is None
            assert value['month']=='2026-09' and value['auto_attempts']==3
    asyncio.run(run())
