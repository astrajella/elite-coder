from services.orchestrator.validation_wrapper import wrap_tool_call
from services.orchestrator.metrics import ORCH_TOOL_CALLS, ORCH_TOOL_LATENCY
import sqlite3, os, threading, json, time
DB = os.getenv('ORCH_DB', './services/orchestrator/orch_runs.db')
os.makedirs(os.path.dirname(DB), exist_ok=True)
_lock = threading.Lock()
def init_db():
    with _lock:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            plan JSON,
            state TEXT,
            created_at REAL,
            updated_at REAL,
            trace JSON
        )''')
        conn.commit(); conn.close()
init_db()

def save_run(run_id, plan, state, trace):
    now = time.time()
    with _lock:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute('INSERT OR REPLACE INTO runs(id,plan,state,created_at,updated_at,trace) VALUES(?,?,?,?,?,?)',
                    (run_id, json.dumps(plan), state, now, now, json.dumps(trace)))
        conn.commit(); conn.close()

def update_run_trace(run_id, state, trace):
    now = time.time()
    with _lock:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute('UPDATE runs SET state=?, updated_at=?, trace=? WHERE id=?', (state, now, json.dumps(trace), run_id))
        conn.commit(); conn.close()

def get_run(run_id):
    with _lock:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute('SELECT id, plan, state, created_at, updated_at, trace FROM runs WHERE id=?', (run_id,))
        row = cur.fetchone()
        conn.close()
        if not row: return None
        return {'id': row[0], 'plan': json.loads(row[1]), 'state': row[2], 'created_at': row[3], 'updated_at': row[4], 'trace': json.loads(row[5])}


def mark_cancelled(run_id):
    with _lock:
        conn = sqlite3.connect(DB); cur = conn.cursor(); cur.execute("UPDATE runs SET state=? WHERE id=?", ('cancelled', run_id)); conn.commit(); conn.close()

def is_cancelled(run_id):
    r = get_run(run_id)
    return r and r.get('state')=='cancelled'
