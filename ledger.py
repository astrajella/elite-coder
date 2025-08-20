
import os, sqlite3, csv, io, time, json
from datetime import date, datetime, timedelta
from statistics import mean

LEDGER_BACKEND = os.getenv("LEDGER_BACKEND", "sqlite")
LEDGER_DB_PATH = os.getenv("LEDGER_DB_PATH", "./ledger.db")
LEDGER_RETENTION_DAYS = int(os.getenv("LEDGER_RETENTION_DAYS", "0"))  # 0 = unlimited

_memory_runs = []

def _init_sqlite():
    conn = sqlite3.connect(LEDGER_DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY,
        persona TEXT,
        tool TEXT,
        duration REAL,
        tokens INTEGER,
        cost REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE INDEX IF NOT EXISTS idx_runs_persona ON runs(persona)""")
    cur.execute("""CREATE INDEX IF NOT EXISTS idx_runs_tool ON runs(tool)""")
    cur.execute("""CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS daily_aggregates (
        id INTEGER PRIMARY KEY,
        date TEXT UNIQUE,
        total_runs INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        total_cost REAL DEFAULT 0.0
    )""")
    cur.execute("""CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_aggregates(date)""")
    conn.commit()
    conn.close()

if LEDGER_BACKEND == "sqlite":
    _init_sqlite()

def log_run(persona, tool, duration, tokens, cost):
    ts = datetime.utcnow().isoformat()
    if LEDGER_BACKEND == "sqlite":
        conn = sqlite3.connect(LEDGER_DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT INTO runs(persona,tool,duration,tokens,cost,timestamp) VALUES(?,?,?,?,?,?)",
            (persona, tool, duration, tokens, cost, ts))
        today = date.today().isoformat()
        cur.execute("""INSERT INTO daily_aggregates(date,total_runs,total_tokens,total_cost)
                       VALUES(?,?,?,?)
                       ON CONFLICT(date) DO UPDATE SET
                         total_runs=total_runs+1,
                         total_tokens=total_tokens+excluded.total_tokens,
                         total_cost=total_cost+excluded.total_cost""", (today,1,tokens,cost))
        conn.commit()
        conn.close()
    else:
        _memory_runs.append({"persona":persona,"tool":tool,"duration":duration,"tokens":tokens,"cost":cost,"timestamp":ts})

def get_runs(limit=100):
    if LEDGER_BACKEND == "sqlite":
        conn = sqlite3.connect(LEDGER_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        query = "SELECT * FROM runs ORDER BY id DESC"
        if limit:
            query += f" LIMIT {limit}"
        cur.execute(query)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    else:
        return list(_memory_runs)[-limit:] if limit else list(_memory_runs)


def export_runs_csv():
    rows=get_runs(limit=None)
    output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=["id","persona","tool","duration","tokens","cost","timestamp"])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return output.getvalue()

def export_daily_csv():
    rows=get_daily()
    output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=["date","total_runs","total_tokens","total_cost"])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return output.getvalue()


def get_stats():
    conn = sqlite3.connect(LEDGER_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    persona_stats = {}
    try:
        cur.execute("SELECT persona, COUNT(*) as total_runs, SUM(tokens) as total_tokens, SUM(cost) as total_cost, AVG(duration) as avg_duration FROM runs GROUP BY persona")
        persona_stats = {r['persona']: dict(r) for r in cur.fetchall()}
    except Exception:
        persona_stats = {}
    tool_stats = {}
    try:
        cur.execute("SELECT tool, COUNT(*) as total_runs, SUM(tokens) as total_tokens, SUM(cost) as total_cost, AVG(duration) as avg_duration FROM runs GROUP BY tool")
        tool_stats = {r['tool']: dict(r) for r in cur.fetchall()}
    except Exception:
        tool_stats = {}
    totals = {"runs": 0, "tokens": 0, "cost": 0}
    try:
        cur.execute("SELECT COUNT(*) as runs, COALESCE(SUM(tokens),0) as tokens, COALESCE(SUM(cost),0) as cost FROM runs")
        totals = dict(cur.fetchone())
    except Exception:
        pass
    conn.close()
    return {"persona": persona_stats, "tool": tool_stats, "totals": totals}


def log_commit(commit_id, patches_meta):
    conn = sqlite3.connect(LEDGER_DB_PATH); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS commits(
        id TEXT PRIMARY KEY, ts REAL, meta TEXT
    )""")
    cur.execute("INSERT OR REPLACE INTO commits(id, ts, meta) VALUES(?,?,?)", (commit_id, time.time(), json.dumps(patches_meta)))
    conn.commit(); conn.close()

def get_history():
    conn = sqlite3.connect(LEDGER_DB_PATH); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS commits(
        id TEXT PRIMARY KEY, ts REAL, meta TEXT
    )""")
    cur.execute("SELECT id, ts, meta FROM commits ORDER BY ts DESC LIMIT 200")
    rows = [{"id": r[0], "ts": r[1], "meta": json.loads(r[2] or "{}")} for r in cur.fetchall()]
    conn.close(); return rows
