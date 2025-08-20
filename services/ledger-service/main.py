import logging
import os
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from datetime import datetime, date
import json
import sqlite3
import csv
import io

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="ledger-service")

# Postgres support: use LEDGER_DB_URL env var; fallback to sqlite DB
LEDGER_DB_URL = os.getenv('LEDGER_DB_URL', None)
USE_POSTGRES = bool(LEDGER_DB_URL)
def init_db_postgres():
    import psycopg2
    conn = psycopg2.connect(LEDGER_DB_URL)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS runs (id SERIAL PRIMARY KEY, persona TEXT, tool TEXT, duration REAL, tokens INTEGER, cost REAL, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS daily_aggregates (id SERIAL PRIMARY KEY, date TEXT UNIQUE, total_runs INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0, total_cost REAL DEFAULT 0.0)''')
    conn.commit(); conn.close()

# modify init_db call
USE_PG = USE_POSTGRES
if USE_PG:
    try:
        init_db_postgres()
    except Exception as e:
        print('Postgres init failed, falling back to sqlite:', e)
        USE_PG = False

DB = os.getenv("LEDGER_DB_PATH", "./ledger_service.db")

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY, persona TEXT, tool TEXT, duration REAL, tokens INTEGER, cost REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS daily_aggregates (
        id INTEGER PRIMARY KEY, date TEXT UNIQUE, total_runs INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0, total_cost REAL DEFAULT 0.0
    )''')
    conn.commit(); conn.close()

init_db()

class RunIn(BaseModel):
    persona: str
    tool: str
    duration: float
    tokens: int
    cost: float

@app.post("/log_run")
async def log_run(run: RunIn):
    conn = sqlite3.connect(DB); cur = conn.cursor()
    cur.execute("INSERT INTO runs(persona,tool,duration,tokens,cost) VALUES(?,?,?,?,?)", (run.persona, run.tool, run.duration, run.tokens, run.cost))
    today = date.today().isoformat()
    cur.execute("""INSERT INTO daily_aggregates(date,total_runs,total_tokens,total_cost) VALUES(?,?,?,?)
                ON CONFLICT(date) DO UPDATE SET total_runs=total_runs+1, total_tokens=total_tokens+excluded.total_tokens, total_cost=total_cost+excluded.total_cost""", (today,1,run.tokens,run.cost))
    conn.commit(); conn.close()
    return {"ok": True}

@app.get("/stats")
async def stats():
    conn = sqlite3.connect(DB); cur = conn.cursor()
    cur.execute("SELECT persona, COUNT(*), SUM(tokens), SUM(cost), AVG(duration) FROM runs GROUP BY persona")
    rows = cur.fetchall(); conn.close()
    data = [{"persona":r[0], "runs":r[1], "tokens":r[2] or 0, "cost":r[3] or 0.0, "avg_duration": r[4] or 0} for r in rows]
    return {"persona_stats": data}

@app.get("/daily")
async def daily():
    conn = sqlite3.connect(DB); cur = conn.cursor()
    cur.execute("SELECT date,total_runs,total_tokens,total_cost FROM daily_aggregates ORDER BY date ASC")
    rows = cur.fetchall(); conn.close()
    out = [{"date":r[0],"total_runs":r[1],"total_tokens":r[2],"total_cost":r[3]} for r in rows]
    return {"daily": out}

@app.get("/daily/export")
async def daily_export():
    conn = sqlite3.connect(DB); cur = conn.cursor()
    cur.execute("SELECT date,total_runs,total_tokens,total_cost FROM daily_aggregates ORDER BY date ASC")
    rows = cur.fetchall(); conn.close()
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(["date","total_runs","total_tokens","total_cost"])
    for r in rows: writer.writerow(r)
    return PlainTextResponse(output.getvalue(), media_type="text/csv")


# helper DB functions to abstract sqlite/postgres
def pg_execute_fetchall(query, params=()):
    import psycopg2, os
    conn = psycopg2.connect(LEDGER_DB_URL); cur = conn.cursor()
    cur.execute(query, params); rows = cur.fetchall(); conn.close(); return rows

def pg_execute(query, params=()):
    import psycopg2, os, json
    conn = psycopg2.connect(LEDGER_DB_URL); cur = conn.cursor()
    cur.execute(query, params); conn.commit(); conn.close()


# Postgres connection pool helper
PG_POOL = None
def init_pg_pool():
    global PG_POOL
    try:
        from psycopg2.pool import SimpleConnectionPool
        PG_POOL = SimpleConnectionPool(1, 10, dsn=LEDGER_DB_URL)
    except Exception as e:
        print('PG pool init failed:', e)
        PG_POOL = None

init_pg_pool()

def pg_execute_fetchall_with_retry(query, params=(), retries=2):
    import time
    for attempt in range(retries+1):
        try:
            if PG_POOL:
                conn = PG_POOL.getconn(); cur = conn.cursor(); cur.execute(query, params); rows = cur.fetchall(); PG_POOL.putconn(conn); return rows
            else:
                return pg_execute_fetchall(query, params)
        except Exception as e:
            last_exc = e
            time.sleep(0.5)
    raise last_exc

def pg_execute_with_retry(query, params=(), retries=2):
    import time
    for attempt in range(retries+1):
        try:
            if PG_POOL:
                conn = PG_POOL.getconn(); cur = conn.cursor(); cur.execute(query, params); conn.commit(); PG_POOL.putconn(conn); return
            else:
                return pg_execute(query, params)
        except Exception as e:
            last_exc = e
            time.sleep(0.5)
    raise last_exc


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
