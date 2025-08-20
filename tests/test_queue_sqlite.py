
import asyncio
from services.orchestrator import queue_sqlite as q

def test_queue_init_event_loop():
    async def _run():
        await q.init()
        await q.enqueue('r1', {'project':'p','steps':[]})
        s = await q.stats()
        assert 'queued' in s and s['queued']>=1
    asyncio.get_event_loop().run_until_complete(_run())
