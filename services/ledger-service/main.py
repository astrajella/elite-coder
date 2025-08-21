import logging
import os
import json
import sqlite3
import csv
import io
from contextlib import contextmanager
from datetime import datetime, date
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Response, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from ..shared.auth import auth_dependency

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="ledger-service")
LEDGER_DB_URL = os.getenv('LEDGER_DB_URL')
USE_PG = bool(LEDGER_DB_URL)
SQLITE_DB_PATH = os.getenv("LEDGER_DB_PATH", "./ledger_service.db")
PG_POOL = None

# --- Database Initialization ---
def init_pg():
    global PG_POOL
    try:
        import psycopg2
        from psycopg2.pool import SimpleConnectionPool
        PG_POOL = SimpleConnectionPool(1, 10, dsn=LEDGER_DB_URL)
        conn = PG_POOL.getconn()
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS runs (id SERIAL PRIMARY KEY, persona TEXT, tool TEXT, duration REAL, tokens INTEGER, cost REAL, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS daily_aggregates (id SERIAL PRIMARY KEY, date DATE UNIQUE, total_runs INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0, total_cost REAL DEFAULT 0.0)''')
        conn.commit()
        PG_POOL.putconn(conn)
        logging.info("PostgreSQL ledger initialized and connection pool created.")
    except (ImportError, psycopg2.OperationalError) as e:
        logging.error(f"PostgreSQL initialization failed: {e}. Service may not function correctly.")
        PG_POOL = None

def init_sqlite():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY, persona TEXT, tool TEXT, duration REAL, tokens INTEGER, cost REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS daily_aggregates (
        id INTEGER PRIMARY KEY, date TEXT UNIQUE, total_runs INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0, total_cost REAL DEFAULT 0.0
    )''')
    conn.commit()
    conn.close()
    logging.info("SQLite ledger initialized.")

@app.on_event("startup")
def startup_event():
    if USE_PG:
        init_pg()
    else:
        init_sqlite()

@contextmanager
def get_db_connection():
    if USE_PG:
        if not PG_POOL:
            raise HTTPException(status_code=503, detail="Database not available")
        conn = PG_POOL.getconn()
        try:
            yield conn
        finally:
            PG_POOL.putconn(conn)
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        try:
            yield conn
        finally:
            conn.close()

# --- Pydantic Models ---
class RunIn(BaseModel):
    persona: str
    tool: str
    duration: float
    tokens: int
    cost: float

# --- API Endpoints ---
@app.post("/log_run", dependencies=[Depends(auth_dependency)])
async def log_run(run: RunIn):
    today = date.today()
    with get_db_connection() as conn:
        cur = conn.cursor()
        if USE_PG:
            cur.execute("INSERT INTO runs(persona,tool,duration,tokens,cost) VALUES(%s,%s,%s,%s,%s)", (run.persona, run.tool, run.duration, run.tokens, run.cost))
            cur.execute("""INSERT INTO daily_aggregates(date,total_runs,total_tokens,total_cost) VALUES(%s,%s,%s,%s)
                        ON CONFLICT(date) DO UPDATE SET total_runs=daily_aggregates.total_runs+1, total_tokens=daily_aggregates.total_tokens+%s, total_cost=daily_aggregates.total_cost+%s""",
                        (today, 1, run.tokens, run.cost, run.tokens, run.cost))
        else:
            cur.execute("INSERT INTO runs(persona,tool,duration,tokens,cost) VALUES(?,?,?,?,?)", (run.persona, run.tool, run.duration, run.tokens, run.cost))
            cur.execute("""INSERT INTO daily_aggregates(date,total_runs,total_tokens,total_cost) VALUES(?,?,?,?)
                        ON CONFLICT(date) DO UPDATE SET total_runs=total_runs+1, total_tokens=total_tokens+excluded.total_tokens, total_cost=total_cost+excluded.total_cost""",
                        (today.isoformat(), 1, run.tokens, run.cost))
        conn.commit()
    return {"ok": True}

@app.get("/stats", dependencies=[Depends(auth_dependency)])
async def stats():
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row if not USE_PG else None
        cur = conn.cursor()
        query = "SELECT persona, COUNT(*), SUM(tokens), SUM(cost), AVG(duration) FROM runs GROUP BY persona"
        cur.execute(query)
        rows = cur.fetchall()

    data = [{"persona":r[0], "runs":r[1], "tokens":r[2] or 0, "cost":r[3] or 0.0, "avg_duration": r[4] or 0} for r in rows]
    return {"persona_stats": data}

@app.get("/daily", dependencies=[Depends(auth_dependency)])
async def daily():
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row if not USE_PG else None
        cur = conn.cursor()
        query = "SELECT date,total_runs,total_tokens,total_cost FROM daily_aggregates ORDER BY date ASC"
        cur.execute(query)
        rows = cur.fetchall()

    out = [{"date": r[0].isoformat() if isinstance(r[0], date) else r[0], "total_runs":r[1], "total_tokens":r[2], "total_cost":r[3]} for r in rows]
    return {"daily": out}

@app.get("/daily/export", dependencies=[Depends(auth_dependency)])
async def daily_export():
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row if not USE_PG else None
        cur = conn.cursor()
        query = "SELECT date,total_runs,total_tokens,total_cost FROM daily_aggregates ORDER BY date ASC"
        cur.execute(query)
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date","total_runs","total_tokens","total_cost"])
    for r in rows:
        # Format date correctly for CSV
        row_list = list(r)
        if isinstance(row_list[0], date):
            row_list[0] = row_list[0].isoformat()
        writer.writerow(row_list)

    return PlainTextResponse(output.getvalue(), media_type="text/csv")

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
