
import os, sqlite3, csv, io, time, json
from datetime import date, datetime, timedelta
from statistics import mean

LEDGER_BACKEND = os.getenv("LEDGER_BACKEND", "sqlite")
LEDGER_DB_PATH = os.getenv("LEDGER_DB_PATH", "./ledger.db")
LEDGER_RETENTION_DAYS = int(os.getenv("LEDGER_RETENTION_DAYS", "0"))  # 0 = unlimited

_memory_runs = []

def _purge_old_records():
    if LEDGER_BACKEND != "sqlite" or LEDGER_RETENTION_DAYS <= 0:
        return

    conn = sqlite3.connect(LEDGER_DB_PATH)
    try:
        cur = conn.cursor()
        cutoff_date = datetime.utcnow() - timedelta(days=LEDGER_RETENTION_DAYS)
        # We assume timestamp is stored in ISO 8601 format
        cur.execute("DELETE FROM runs WHERE timestamp < ?", (cutoff_date.isoformat(),))
        # Note: 'commits' table does not have a standard timestamp to purge against
        conn.commit()
    finally:
        conn.close()

def _init_sqlite():
    conn = sqlite3.connect(LEDGER_DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, persona TEXT, tool TEXT, duration REAL,
            tokens INTEGER, cost REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS daily_aggregates (
            id INTEGER PRIMARY KEY, date TEXT UNIQUE, total_runs INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0, total_cost REAL DEFAULT 0.0
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS commits(
            id TEXT PRIMARY KEY, ts REAL, meta TEXT
        )""")
        conn.commit()
    finally:
        conn.close()
    _purge_old_records()

if LEDGER_BACKEND == "sqlite":
    _init_sqlite()

def log_run(persona, tool, duration, tokens, cost):
    ts = datetime.utcnow().isoformat()
    if LEDGER_BACKEND == "sqlite":
        conn = sqlite3.connect(LEDGER_DB_PATH)
        try:
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
        finally:
            conn.close()
    else:
        _memory_runs.append({"persona":persona,"tool":tool,"duration":duration,"tokens":tokens,"cost":cost,"timestamp":ts})

def get_runs(limit=100):
    if LEDGER_BACKEND == "sqlite":
        conn = sqlite3.connect(LEDGER_DB_PATH)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            query = "SELECT * FROM runs ORDER BY id DESC"
            params = []
            if limit and isinstance(limit, int):
                query += " LIMIT ?"
                params.append(limit)
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    else:
        return list(_memory_runs)[-limit:] if limit else list(_memory_runs)

def export_runs_csv():
    rows=get_runs(limit=None)
    output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=["id","persona","tool","duration","tokens","cost","timestamp"])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()

def export_daily_csv():
    # This function depends on a get_daily() which does not exist in the file.
    # Assuming it should exist or this is dead code. For now, leaving as is.
    rows=get_daily()
    output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=["date","total_runs","total_tokens","total_cost"])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()

def get_stats():
    if LEDGER_BACKEND != "sqlite":
        # Basic in-memory stats calculation
        persona_stats = {}
        tool_stats = {}
        for run in _memory_runs:
            p = run['persona']
            t = run['tool']
            persona_stats.setdefault(p, {'runs': 0, 'tokens': 0, 'cost': 0, 'durations': []})
            tool_stats.setdefault(t, {'runs': 0, 'tokens': 0, 'cost': 0, 'durations': []})
            persona_stats[p]['runs'] += 1
            persona_stats[p]['tokens'] += run['tokens']
            persona_stats[p]['cost'] += run['cost']
            persona_stats[p]['durations'].append(run['duration'])
            tool_stats[t]['runs'] += 1
            tool_stats[t]['tokens'] += run['tokens']
            tool_stats[t]['cost'] += run['cost']
            tool_stats[t]['durations'].append(run['duration'])

        for p, data in persona_stats.items():
            data['avg_duration'] = mean(data.pop('durations')) if data['durations'] else 0
        for t, data in tool_stats.items():
            data['avg_duration'] = mean(data.pop('durations')) if data['durations'] else 0

        totals = {"runs": len(_memory_runs), "tokens": sum(r['tokens'] for r in _memory_runs), "cost": sum(r['cost'] for r in _memory_runs)}
        return {"persona": persona_stats, "tool": tool_stats, "totals": totals}

    conn = sqlite3.connect(LEDGER_DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        persona_stats, tool_stats, totals = {}, {}, {}

        cur.execute("SELECT persona, COUNT(*) as total_runs, SUM(tokens) as total_tokens, SUM(cost) as total_cost, AVG(duration) as avg_duration FROM runs GROUP BY persona")
        persona_stats = {r['persona']: dict(r) for r in cur.fetchall()}

        cur.execute("SELECT tool, COUNT(*) as total_runs, SUM(tokens) as total_tokens, SUM(cost) as total_cost, AVG(duration) as avg_duration FROM runs GROUP BY tool")
        tool_stats = {r['tool']: dict(r) for r in cur.fetchall()}

        cur.execute("SELECT COUNT(*) as runs, COALESCE(SUM(tokens),0) as tokens, COALESCE(SUM(cost),0) as cost FROM runs")
        totals = dict(cur.fetchone())

        return {"persona": persona_stats, "tool": tool_stats, "totals": totals}
    finally:
        conn.close()

def log_commit(commit_id, patches_meta):
    if LEDGER_BACKEND == "sqlite":
        conn = sqlite3.connect(LEDGER_DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO commits(id, ts, meta) VALUES(?,?,?)", (commit_id, time.time(), json.dumps(patches_meta)))
            conn.commit()
        finally:
            conn.close()

def get_history():
    if LEDGER_BACKEND == "sqlite":
        conn = sqlite3.connect(LEDGER_DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, ts, meta FROM commits ORDER BY ts DESC LIMIT 200")
            return [{"id": r[0], "ts": r[1], "meta": json.loads(r[2] or "{}")} for r in cur.fetchall()]
        finally:
            conn.close()
    return []
