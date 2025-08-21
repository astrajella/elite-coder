import requests, os, time
import pytest
BASE = os.getenv('LEDGER_URL','http://127.0.0.1:8003')

@pytest.mark.skip(reason="Integration test that requires a running ledger-service")
def test_ledger_stats():
    r = requests.get(f'{BASE}/stats')
    assert r.status_code == 200


def get_stats():
    import sqlite3
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


def get_history(limit=50):
    import sqlite3, json
    conn = sqlite3.connect(LEDGER_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute("CREATE TABLE IF NOT EXISTS commits(id INTEGER PRIMARY KEY, ts TEXT, message TEXT, artifact_path TEXT)")
        cur.execute("SELECT ts, message, artifact_path FROM commits ORDER BY id DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        conn.close()
