
import asyncio, time
from services.orchestrator import queue_sqlite as q

def test_fairness_and_reaper_smoke():
    async def _run():
        await q.init()
        # ensure clean-ish slate (not deleting DB for simplicity)
        await q.set_project_weight('A', 1)
        await q.set_project_weight('B', 3)
        # enqueue
        await q.enqueue('rA1', {'project':'A','steps':[]})
        await q.enqueue('rB1', {'project':'B','steps':[]})
        await q.enqueue('rB2', {'project':'B','steps':[]})
        c1 = await q.claim_next_fair('w1', fairness=True)
        assert c1 and c1['project'] in ('A','B')
        # mark as running then stale to test reaper
        await q.reap_stale(heartbeat_timeout=0.0)
        stats = await q.stats()
        assert stats['queued'] >= 1
    asyncio.get_event_loop().run_until_complete(_run())
