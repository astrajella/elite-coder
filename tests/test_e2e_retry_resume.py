
import asyncio, os
from services.orchestrator import queue_sqlite as q
from services.orchestrator.scheduler import execute_plan

def test_retry_resume_e2e():
    async def _run():
        await q.init()
        run_id = 'run-retry-1'
        plan = {'project':'demo','steps':[{'id':'s1'},{'id':'s2'}]}
        os.environ['ORCH_INJECT_FAIL'] = '2'  # first two tool calls will fail validation
        os.environ['ORCH_MAX_ATTEMPTS'] = '3'
        os.environ['ORCH_RETRY_BACKOFF'] = '0'  # speed up test
        try:
            await execute_plan(run_id, plan)
            ok = True
        except Exception:
            ok = False
        # With two injected failures and max_attempts=3, execute_plan should eventually succeed
        assert ok is True
    asyncio.get_event_loop().run_until_complete(_run())
