from services.orchestrator.validation_wrapper import wrap_tool_call
from services.orchestrator.metrics import ORCH_TOOL_CALLS, ORCH_TOOL_LATENCY

import os, json, time, asyncio, aiosqlite
from typing import Optional, Dict, Any

DB_PATH = os.getenv('ORCH_QUEUE_DB', '/tmp/orchestrator_queue.db')

INIT_SQL = '''
CREATE TABLE IF NOT EXISTS project_weights (project TEXT PRIMARY KEY, weight INTEGER NOT NULL DEFAULT 1, served_count INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL DEFAULT (strftime('%s','now')));

CREATE TABLE IF NOT EXISTS runs_queue (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL, -- queued|running|done|failed
  project TEXT,
  plan_json TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  locked_by TEXT,
  priority INTEGER NOT NULL DEFAULT 0,
  enqueued_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_queue_status ON runs_queue(status);
CREATE INDEX IF NOT EXISTS idx_runs_queue_priority ON runs_queue(priority, enqueued_at);
'''

async def init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(INIT_SQL)
        await db.commit()

async def enqueue(run_id: str, plan: Dict[str, Any], project: Optional[str] = None, priority: int = 0):
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT OR REPLACE INTO runs_queue (id,status,project,plan_json,attempts,locked_by,priority,enqueued_at,updated_at) VALUES (?,?,?,?,?,?,?, ?,?)',
            (run_id, 'queued', project or plan.get('project'), json.dumps(plan), 0, None, priority, now, now)
        )
        await db.commit()
    return {'ok': True, 'run_id': run_id}

async def claim_next(worker_id: str):
    # Fair scheduling: pick lowest priority, then oldest enqueued; skip locked
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""            SELECT id, project, plan_json FROM runs_queue
            WHERE status='queued' AND (locked_by IS NULL OR locked_by='')
            ORDER BY priority ASC, enqueued_at ASC
            LIMIT 1
        """) as cur:
            row = await cur.fetchone()
            if not row:
                return None
        # lock it
        now = time.time()
        await db.execute('UPDATE runs_queue SET status=?, locked_by=?, updated_at=? WHERE id=? AND status="queued"',
                         ('running', worker_id, now, row['id']))
        await db.commit()
        return {'run_id': row['id'], 'project': row['project'], 'plan': json.loads(row['plan_json'])}

async def heartbeat(run_id: str, worker_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE runs_queue SET updated_at=? WHERE id=? AND locked_by=?', (time.time(), run_id, worker_id))
        await db.commit()

async def complete(run_id: str, worker_id: str, ok: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        status = 'done' if ok else 'failed'
        await db.execute('UPDATE runs_queue SET status=?, locked_by=NULL, updated_at=? WHERE id=? AND locked_by=?', (status, time.time(), run_id, worker_id))
        await db.commit()

async def requeue(run_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE runs_queue SET status=?, locked_by=NULL, attempts=attempts+1, updated_at=? WHERE id=?', ('queued', time.time(), run_id))
        await db.commit()

async def stats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        out = {}
        for st in ('queued','running','done','failed'):
            async with db.execute('SELECT COUNT(*) c FROM runs_queue WHERE status=?', (st,)) as cur:
                r = await cur.fetchone()
                out[st] = r['c']
        return out


async def set_project_weight(project: str, weight: int = 1):
    weight = max(1, int(weight))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO project_weights(project, weight, served_count, updated_at) VALUES(?,?,COALESCE((SELECT served_count FROM project_weights WHERE project=?),0), strftime("%s","now")) ON CONFLICT(project) DO UPDATE SET weight=excluded.weight, updated_at=excluded.updated_at', (project, weight, project))
        await db.commit()

async def get_project_weights():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        out = {}
        async with db.execute('SELECT project, weight, served_count FROM project_weights') as cur:
            async for row in cur:
                out[row['project']] = {'weight': row['weight'], 'served_count': row['served_count']}
        return out

async def _inc_served(project: str):
    if not project: 
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO project_weights(project, weight, served_count, updated_at) VALUES(?,1,1,strftime("%s","now")) ON CONFLICT(project) DO UPDATE SET served_count=project_weights.served_count+1, updated_at=strftime("%s","now")', (project,))
        await db.commit()


async def reap_stale(heartbeat_timeout: float = 120.0):
    # Any running item with updated_at older than now - timeout is re-queued
    cutoff = time.time() - float(heartbeat_timeout)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE runs_queue SET status="queued", locked_by=NULL WHERE status="running" AND updated_at < ?', (cutoff,))
        await db.commit()

async def _pick_project_for_fairness(db):
    # Pick the project among queued items using min(served_count / weight) to balance
    db.row_factory = aiosqlite.Row
    projects = []
    async with db.execute('SELECT project, COUNT(*) as cnt FROM runs_queue WHERE status="queued" GROUP BY project') as cur:
        async for row in cur:
            projects.append((row['project'] or 'default', row['cnt']))
    if not projects:
        return None
    weights = {}
    async with db.execute('SELECT project, weight, served_count FROM project_weights') as cur:
        async for r in cur:
            weights[r['project']] = (r['weight'], r['served_count'])
    # Compute score = served_count / weight (lower is preferred)
    best = None; best_score = None
    for (p, cnt) in projects:
        w, s = weights.get(p, (1, 0))
        score = (s or 0) / max(1, w)
        if best is None or score < best_score:
            best, best_score = p, score
    return best

async def claim_next_fair(worker_id: str, fairness: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        if fairness:
            chosen = await _pick_project_for_fairness(db)
        else:
            chosen = None

        if chosen:
            db.row_factory = aiosqlite.Row
            async with db.execute("""                SELECT id, project, plan_json FROM runs_queue
                WHERE status='queued' AND (locked_by IS NULL OR locked_by='') AND (project=? OR (project IS NULL AND ?='default'))
                ORDER BY priority ASC, enqueued_at ASC
                LIMIT 1
            """, (chosen, chosen)) as cur:
                row = await cur.fetchone()
        else:
            db.row_factory = aiosqlite.Row
            async with db.execute("""                SELECT id, project, plan_json FROM runs_queue
                WHERE status='queued' AND (locked_by IS NULL OR locked_by='')
                ORDER BY priority ASC, enqueued_at ASC
                LIMIT 1
            """) as cur:
                row = await cur.fetchone()

        if not row:
            return None
        now = time.time()
        await db.execute('UPDATE runs_queue SET status=?, locked_by=?, updated_at=? WHERE id=? AND status="queued"',
                         ('running', worker_id, now, row['id']))
        await db.commit()
        # bump fairness served count
        await _inc_served(row['project'] or 'default')
        return {'run_id': row['id'], 'project': row['project'], 'plan': json.loads(row['plan_json'])}


import aiosqlite, time

async def init_run_steps(db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS run_steps(
            run_id TEXT,
            step_id TEXT,
            status TEXT,
            attempts INTEGER DEFAULT 0,
            updated_at REAL,
            trace_id TEXT,
            PRIMARY KEY(run_id, step_id)
        )''')
        await db.commit()

async def step_get(run_id: str, step_id: str, db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("SELECT status, attempts, updated_at FROM run_steps WHERE run_id=? AND step_id=?", (run_id, step_id))
        row = await cur.fetchone()
        return row

async def step_begin(run_id: str, step_id: str, db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        now = time.time()
        await db.execute("INSERT OR IGNORE INTO run_steps(run_id, step_id, status, attempts, updated_at) VALUES(?,?,?,?,?)", (run_id, step_id, 'running', 0, now))
        await db.execute("UPDATE run_steps SET status='running', attempts=attempts+1, updated_at=? WHERE run_id=? AND step_id=?", (now, run_id, step_id))
        await db.commit()

async def step_complete(run_id: str, step_id: str, ok: bool, db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        now = time.time()
        status = 'done' if ok else 'failed'
        await db.execute("INSERT OR IGNORE INTO run_steps(run_id, step_id, status, attempts, updated_at) VALUES(?,?,?,?,?)", (run_id, step_id, status, 0, now))
        await db.execute("UPDATE run_steps SET status=?, updated_at=? WHERE run_id=? AND step_id=?", (status, now, run_id, step_id))
        await db.commit()

async def step_list(run_id: str, limit: int = 200, offset: int = 0, db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("SELECT step_id, status, attempts, updated_at, trace_id FROM run_steps WHERE run_id=? ORDER BY updated_at LIMIT ? OFFSET ?", (run_id, limit, offset))
        rows = await cur.fetchall()
        return [{'step_id':r[0], 'status':r[1], 'attempts':r[2], 'updated_at':r[3], 'trace_id': r[4]} for r in rows]


import aiosqlite, time, os, uuid

async def init_leases(db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS leases(
            run_id TEXT,
            step_id TEXT,
            lease_id TEXT,
            owner TEXT,
            expires_at REAL,
            trace_id TEXT,
            PRIMARY KEY(run_id, step_id)
        )''')
        await db.commit()

async def lease_acquire(run_id: str, step_id: str, owner: str, ttl_sec: float = 30.0, db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    now = time.time()
    lease_id = str(uuid.uuid4())
    async with aiosqlite.connect(db_path) as db:
        # if existing lease expired, take it
        cur = await db.execute("SELECT lease_id, expires_at FROM leases WHERE run_id=? AND step_id=?", (run_id, step_id))
        row = await cur.fetchone()
        if row and row[1] and row[1] > now:
            return None  # someone else holds a valid lease
        await db.execute("INSERT OR REPLACE INTO leases(run_id, step_id, lease_id, owner, expires_at) VALUES(?,?,?,?,?)",
                         (run_id, step_id, lease_id, owner, now + ttl_sec))
        await db.commit()
    return lease_id

async def lease_renew(run_id: str, step_id: str, lease_id: str, ttl_sec: float = 30.0, db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE leases SET expires_at=? WHERE run_id=? AND step_id=? AND lease_id=?",
                         (time.time()+ttl_sec, run_id, step_id, lease_id))
        await db.commit()

async def lease_release(run_id: str, step_id: str, lease_id: str, db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM leases WHERE run_id=? AND step_id=? AND lease_id=?", (run_id, step_id, lease_id))
        await db.commit()

async def requeue_orphans(db_path=None):
    # clear expired leases so steps are eligible again
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM leases WHERE expires_at < ?", (time.time(),))
        await db.commit()


async def init_executions(db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS executions(
            run_id TEXT,
            step_id TEXT,
            idem_key TEXT,
            created_at REAL,
            PRIMARY KEY(run_id, step_id, idem_key)
        )''')
        await db.commit()

async def execution_seen(run_id: str, step_id: str, idem_key: str, db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("SELECT 1 FROM executions WHERE run_id=? AND step_id=? AND idem_key=?", (run_id, step_id, idem_key))
        return await cur.fetchone() is not None

async def execution_mark(run_id: str, step_id: str, idem_key: str, db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        await db.execute("INSERT OR IGNORE INTO executions(run_id, step_id, idem_key, created_at) VALUES(?,?,?,?)",
                         (run_id, step_id, idem_key, time.time()))
        await db.commit()


async def step_set_trace(run_id: str, step_id: str, trace_id: str, db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE run_steps SET trace_id=? WHERE run_id=? AND step_id=?", (trace_id, run_id, step_id))
        await db.commit()


async def step_list_all(limit: int = 1000, offset: int = 0, db_path=None):
    db_path = db_path or os.getenv('ORCH_QUEUE_DB','/tmp/orchestrator_queue.db')
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("SELECT run_id, step_id, status, attempts, updated_at, trace_id FROM run_steps ORDER BY updated_at LIMIT ? OFFSET ?", (limit, offset))
        rows = await cur.fetchall()
        return [{'run_id':r[0], 'step_id':r[1], 'status':r[2], 'attempts':r[3], 'updated_at':r[4], 'trace_id': r[5]} for r in rows]
