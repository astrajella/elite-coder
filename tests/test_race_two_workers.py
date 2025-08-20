
import asyncio, os, time
from services.orchestrator.queue_sqlite import init, init_run_steps, init_leases, init_executions, lease_acquire, lease_renew, lease_release, execution_seen, execution_mark

async def worker(run_id, step_id, owner, delay=0.0):
    await asyncio.sleep(delay)
    lease = await lease_acquire(run_id, step_id, owner, ttl_sec=0.5)
    if not lease:
        return 'no-lease'
    try:
        # pretend to work and renew lease
        for _ in range(2):
            await asyncio.sleep(0.25)
            await lease_renew(run_id, step_id, lease, ttl_sec=0.5)
        key = f"{run_id}:{step_id}:race"
        already = await execution_seen(run_id, step_id, key)
        if not already:
            await execution_mark(run_id, step_id, key)
            result = 'committed'
        else:
            result = 'skipped'
    finally:
        await lease_release(run_id, step_id, lease)
    return result

def test_two_workers_race():
    async def _run():
        await init(); await init_run_steps(); await init_leases(); await init_executions()
        run_id, step_id = 'race-run', 'race-step'
        # Two concurrent workers
        res = await asyncio.gather(worker(run_id, step_id, 'w1', 0.0),
                                   worker(run_id, step_id, 'w2', 0.05))
        # Exactly one commits
        assert res.count('committed') == 1
        assert res.count('no-lease') + res.count('skipped') == 1
    asyncio.get_event_loop().run_until_complete(_run())
