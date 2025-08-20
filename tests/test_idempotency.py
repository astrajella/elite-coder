
import asyncio, os
from services.orchestrator import queue_sqlite as q
from services.orchestrator.scheduler import execute_plan

def test_idempotent_steps():
    async def _run():
        await q.init()
        await q.init_run_steps()
        run_id = 'run-idem-1'
        plan = {'project':'demo','steps':[{'id':'s1'},{'id':'s2'}]}
        os.environ['ORCH_INJECT_FAIL'] = '0'
        await execute_plan(run_id, plan)
        steps = await q.step_list(run_id)
        assert all(s['status']=='done' for s in steps)
        # Re-run should skip both steps
        await execute_plan(run_id, plan)
        steps2 = await q.step_list(run_id)
        assert len(steps2) == len(steps)
    asyncio.get_event_loop().run_until_complete(_run())
