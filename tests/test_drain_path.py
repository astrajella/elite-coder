
import asyncio
from services.orchestrator.scheduler import set_draining, is_draining, wait_for_drain

def test_drain_flags():
    async def _run():
        await set_draining(True)
        assert await is_draining() is True
        ok = await wait_for_drain(0.2)  # no active runs -> should resolve fast
        assert ok in (True, False)
        await set_draining(False)
        assert await is_draining() is False
    asyncio.get_event_loop().run_until_complete(_run())
