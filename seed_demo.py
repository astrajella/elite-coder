#!/usr/bin/env python3
import os, sqlite3
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
USER_DB = os.getenv('AGENT_USER_DB','./services/agent-core/agent_users.db')
os.makedirs(os.path.dirname(USER_DB), exist_ok=True)
conn = sqlite3.connect(USER_DB)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, hashed_password TEXT, role TEXT)")
try:
    hashed = pwd_context.hash("devpassword")
    cur.execute("INSERT OR IGNORE INTO users(username, hashed_password, role) VALUES(?,?,?)", ("dev", hashed, "developer"))
    conn.commit()
    print("Seeded default developer user 'dev'")
except Exception as e:
    print("User seed error:", e)
finally:
    conn.close()
