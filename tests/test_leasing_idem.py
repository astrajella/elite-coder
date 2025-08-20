
import asyncio, os
from services.orchestrator.queue_sqlite import init, init_run_steps, init_leases, init_executions, lease_acquire, lease_release, execution_mark, execution_seen

def test_leases_and_idem():
    async def _run():
        await init(); await init_run_steps(); await init_leases(); await init_executions()
        run_id, step_id = 'r1', 's1'
        l1 = await lease_acquire(run_id, step_id, 'w1', ttl_sec=1.0)
        assert l1 is not None
        # Can't acquire second lease until first released or expired
        l2 = await lease_acquire(run_id, step_id, 'w2', ttl_sec=1.0)
        assert l2 is None
        await lease_release(run_id, step_id, l1)
        l3 = await lease_acquire(run_id, step_id, 'w2', ttl_sec=1.0)
        assert l3 is not None
        key = f"{run_id}:{step_id}:1"
        await execution_mark(run_id, step_id, key)
        seen = await execution_seen(run_id, step_id, key)
        assert seen is True
    asyncio.get_event_loop().run_until_complete(_run())
