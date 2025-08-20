
import os, sqlite3, json, time
from typing import Optional, Dict, Any, List

LEDGER_BACKEND = os.getenv("LEDGER_BACKEND","sqlite")
LEDGER_DB_PATH = os.getenv("LEDGER_DB_PATH","./services/ledger/ledger.db")

def init_db():
    if LEDGER_BACKEND != "sqlite":
        return
    os.makedirs(os.path.dirname(LEDGER_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(LEDGER_DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS runs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL DEFAULT (strftime('%s','now')),
        run_id TEXT,
        persona TEXT,
        tool TEXT,
        tokens REAL,
        cost REAL,
        duration REAL,
        status TEXT,
        meta TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS patches(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL DEFAULT (strftime('%s','now')),
        run_id TEXT,
        path TEXT,
        size_bytes INTEGER
    )""")
    conn.commit()
    conn.close()

def record_run(run_id: str, persona: str, tool: str, tokens: float, cost: float, duration: float, status: str, meta: Dict[str,Any]):
    if LEDGER_BACKEND != "sqlite":
        return
    conn = sqlite3.connect(LEDGER_DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO runs(run_id,persona,tool,tokens,cost,duration,status,meta) VALUES(?,?,?,?,?,?,?,?)",
                (run_id, persona, tool, tokens, cost, duration, status, json.dumps(meta or {})))
    conn.commit()
    conn.close()

def record_patches(run_id: str, applied: List[Dict[str,Any]]):
    if LEDGER_BACKEND != "sqlite":
        return
    conn = sqlite3.connect(LEDGER_DB_PATH)
    cur = conn.cursor()
    for a in applied:
        cur.execute("INSERT INTO patches(run_id,path,size_bytes) VALUES(?,?,?)", (run_id, a['path'], int(a.get('bytes',0))))
    conn.commit()
    conn.close()

def get_stats():
    if LEDGER_BACKEND != "sqlite":
        return {"persona":{}, "tool":{}, "totals":{}}
    conn = sqlite3.connect(LEDGER_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT persona, COUNT(*) as total_runs, SUM(tokens) as total_tokens, SUM(cost) as total_cost, AVG(duration) as avg_duration FROM runs GROUP BY persona")
    persona_stats = {r['persona']: dict(r) for r in cur.fetchall()}
    cur.execute("SELECT tool, COUNT(*) as total_runs, SUM(tokens) as total_tokens, SUM(cost) as total_cost, AVG(duration) as avg_duration FROM runs GROUP BY tool")
    tool_stats = {r['tool']: dict(r) for r in cur.fetchall()}
    cur.execute("SELECT COUNT(*) as runs, SUM(tokens) as tokens, SUM(cost) as cost FROM runs")
    totals = dict(cur.fetchone() or {"runs":0,"tokens":0,"cost":0})
    conn.close()
    return {"persona": persona_stats, "tool": tool_stats, "totals": totals}
