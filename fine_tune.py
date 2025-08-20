import sqlite3
import os
import time
import threading
import json

DB = os.getenv('FINE_TUNE_DB', './fine_tune.db')
db_dir = os.path.dirname(DB)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY,
            dataset_path TEXT,
            base_model TEXT,
            adapter TEXT,
            status TEXT,
            result TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def queue_job(dataset_path, base_model, adapter='lora_adapter'):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO jobs(dataset_path,base_model,adapter,status) VALUES(?,?,?,?)',
        (dataset_path, base_model, adapter, 'queued')
    )
    jid = cur.lastrowid
    conn.commit()
    conn.close()
    return jid

def get_job(jid):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('SELECT id,dataset_path,base_model,adapter,status,result,created_at FROM jobs WHERE id=?', (jid,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    keys = ['id', 'dataset_path', 'base_model', 'adapter', 'status', 'result', 'created_at']
    return dict(zip(keys, row))

def worker_loop(poll_interval=2.0):
    while True:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("SELECT id,dataset_path,base_model,adapter FROM jobs WHERE status='queued' ORDER BY id ASC LIMIT 1")
        row = cur.fetchone()
        if row:
            jid, dataset, base, adapter = row
            cur.execute('UPDATE jobs SET status=? WHERE id=?', ('running', jid))
            conn.commit()
            # simulate training
            time.sleep(2)
            result = {'status': 'done', 'details': f'Trained {base} with {adapter} on {dataset}'}
            cur.execute('UPDATE jobs SET status=?, result=? WHERE id=?', ('done', json.dumps(result), jid))
            conn.commit()
        conn.close()
        time.sleep(poll_interval)

# Initialize the database
init_db()

# start background thread
_thread = threading.Thread(target=worker_loop, daemon=True)
_thread.start()
