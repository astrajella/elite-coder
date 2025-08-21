import logging
from fastapi import FastAPI, Header, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import sqlite3, uuid
import os
import structlog
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, time, httpx, json

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="agent-core")

# Simple user store (SQLite) for auth/RBAC
USER_DB = os.getenv('AGENT_USER_DB','./agent_users.db')
AGENT_USER_DB_URL = os.getenv('AGENT_USER_DB_URL', None)
USE_PG_USERS = bool(AGENT_USER_DB_URL)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv('JWT_SECRET')
if not SECRET_KEY:
    raise SystemExit('JWT_SECRET is required')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def init_user_db():
    global USE_PG_USERS
    if USE_PG_USERS:
        try:
            import psycopg2
            conn = psycopg2.connect(AGENT_USER_DB_URL)
            cur = conn.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE, hashed_password TEXT, role TEXT)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS password_resets (token TEXT PRIMARY KEY, username TEXT, expires TIMESTAMP)''')
            conn.commit(); conn.close()
            return
        except Exception as e:
            print('Postgres user DB init failed, falling back to sqlite:', e)
            USE_PG_USERS = False

    conn = sqlite3.connect(USER_DB)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, hashed_password TEXT, role TEXT)''')
    conn.commit(); conn.close()

@app.on_event("startup")
async def startup_event():
    init_user_db()
    init_csrf_table()

class UserIn(BaseModel):
    username: str
    password: str
    role: str = 'developer'

class Token(BaseModel):
    access_token: str
    token_type: str

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def get_password_hash(pw):
    return pwd_context.hash(pw)

def create_access_token(data: dict):
    to_encode = data.copy()
    import datetime
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail='Missing authorization')
    token = authorization.split()[-1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get('sub')
        role = payload.get('role')
        if username is None:
            raise HTTPException(status_code=401, detail='Invalid token')
        return {'username': username, 'role': role}
    except JWTError:
        raise HTTPException(status_code=401, detail='Invalid token')

def require_role(user, allowed):
    if user.get('role') not in allowed:
        raise HTTPException(status_code=403, detail='Forbidden')


LEDGER_URL = os.getenv("LEDGER_SERVICE_URL","http://localhost:8003")
JWT_SECRET = os.getenv('JWT_SECRET')

class ToolCall(BaseModel):
    tool: str
    payload: dict
    persona: str = "coder"

@app.post("/invoke_tool")
async def invoke_tool(call: ToolCall, authorization: str = Header(None), user = Depends(get_current_user), x_csrf_token: str = Header(None)):
    require_role(user, ['developer','admin'])
    if not x_csrf_token or not validate_csrf_for_user(user.get('username'), x_csrf_token):
        raise HTTPException(status_code=403, detail='invalid csrf token')
    start = time.time()
    # route to providers or retrieval as simple mock
    tool = call.tool
    persona = call.persona
    result = {"ok": True, "tool": tool, "persona": persona, "output": "stubbed"}
    # post a run to ledger service asynchronously
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{LEDGER_URL}/log_run", json={"persona":persona,"tool":tool,"duration":0.1,"tokens":10,"cost":0.001})
    except httpx.RequestError as e:
        logging.error(f"Failed to log run to ledger service: {e}")
    duration = time.time()-start
    return {"id":"tid","status":"ok","duration":duration,"persona":persona,"tool":tool,"result":result}


from fastapi.responses import StreamingResponse
import importlib, asyncio

@app.get('/stream')
async def stream_provider(provider: str = 'openrouter', prompt: str = 'Hello', authorization: str = Header(None), user = Depends(get_current_user), x_csrf_token: str = Header(None)):
    # very light auth check
    require_role(user, ['developer','admin'])
    if not x_csrf_token or not validate_csrf_for_user(user.get('username'), x_csrf_token):
        raise HTTPException(status_code=403, detail='invalid csrf token')
    # dynamically import provider adapter
    adapter_name = f"providers.{provider}_adapter"
    try:
        mod = importlib.import_module(adapter_name)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Provider adapter not found: {provider}")
    async def event_generator():
        # If adapter has generate_stream, iterate it
        if hasattr(mod, 'generate_stream'):
            for chunk in mod.generate_stream(prompt):
                data = json.dumps({'chunk': chunk})
                yield f"data: {data}\n\n"
                await asyncio.sleep(0.05)
        else:
            # fallback: call generate and stream split
            resp = mod.generate(prompt)
            text = ''
            if isinstance(resp, dict):
                text = resp.get('text') or (resp.get('choices',[{}])[0].get('text','') if resp.get('choices') else str(resp))
            else:
                text = str(resp)
            for i in range(0, len(text), 120):
                yield f"data: {json.dumps({'chunk': text[i:i+120]})}\n\n"
                await asyncio.sleep(0.05)
    return StreamingResponse(event_generator(), media_type='text/event-stream')


@app.post('/auth/register')
async def register_user(u: UserIn):
    conn = None
    try:
        conn = sqlite3.connect(USER_DB)
        cur = conn.cursor()
        cur.execute('INSERT INTO users(username,hashed_password,role) VALUES(?,?,?)', (u.username, get_password_hash(u.password), u.role))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists")
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if conn:
            conn.close()
    return {'ok': True}

@app.post('/auth/login')
async def login(form: OAuth2PasswordRequestForm = Depends()):
    conn = None
    try:
        conn = sqlite3.connect(USER_DB)
        cur = conn.cursor()
        cur.execute('SELECT username, hashed_password, role FROM users WHERE username=?', (form.username,))
        row = cur.fetchone()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if conn:
            conn.close()

    if not row or not verify_password(form.password, row[1]):
        raise HTTPException(status_code=400, detail='Incorrect username or password')

    username, _, role = row
    access_token = create_access_token({'sub': username, 'role': role})

    # create refresh token and store
    import uuid, datetime
    refresh_token = str(uuid.uuid4())
    expires = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat()

    conn = None
    try:
        conn = sqlite3.connect(USER_DB)
        cur = conn.cursor()
        cur.execute('INSERT OR REPLACE INTO refresh_tokens(token,username,expires) VALUES(?,?,?)', (refresh_token, username, expires))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to store refresh token for user {username}: {e}")
    finally:
        if conn:
            conn.close()

    return {'access_token': access_token, 'token_type': 'bearer', 'refresh_token': refresh_token, 'refresh_expires': expires}


from typing import List, Dict
from fastapi import Body
ARTIFACTS_DIR = os.getenv('ARTIFACTS_DIR','./artifacts')
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

class FilePatch(BaseModel):
    path: str
    type: str
    content: str

@app.post('/commit')
async def commit_patches(commit_message: str = Body(...), patches: List[FilePatch] = Body(...), user = Depends(get_current_user), x_csrf_token: str = Header(None)):
    # require role
    require_role(user, ['developer','admin'])
    if not x_csrf_token or not validate_csrf_for_user(user.get('username'), x_csrf_token):
        raise HTTPException(status_code=403, detail='invalid csrf token')
    applied = []
    for p in patches:
        # safely write file relative to ARTIFACTS_DIR
        safe_path = os.path.normpath(os.path.join(ARTIFACTS_DIR, p.path))
        if not safe_path.startswith(os.path.abspath(ARTIFACTS_DIR)):
            raise HTTPException(status_code=400, detail='Invalid path')
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(p.content)
        applied.append(p.path)
    # Log commit to ledger service
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{LEDGER_URL}/log_run", json={"persona":"coder","tool":"commit","duration":0.0,"tokens":0,"cost":0.0})
    except httpx.RequestError as e:
        logging.error(f"Failed to log commit to ledger service: {e}")
    return {"commit_message": commit_message, "applied": applied, "ok": True}


from fine_tune import queue_job, get_job
class FineTuneReq(BaseModel):
    dataset_path: str
    base_model: str
    adapter: str = 'lora_adapter'

@app.post('/fine_tune')
async def queue_fine_tune(req: FineTuneReq, user = Depends(get_current_user), x_csrf_token: str = Header(None)):
    require_role(user, ['developer','admin'])
    if not x_csrf_token or not validate_csrf_for_user(user.get('username'), x_csrf_token):
        raise HTTPException(status_code=403, detail='invalid csrf token')
    jid = queue_job(req.dataset_path, req.base_model, req.adapter)
    return {'job_id': jid, 'status': 'queued'}

@app.get('/fine_tune/{job_id}')
async def get_fine_tune(job_id: int, user = Depends(get_current_user), x_csrf_token: str = Header(None)):
    require_role(user, ['developer','admin'])
    if not x_csrf_token or not validate_csrf_for_user(user.get('username'), x_csrf_token):
        raise HTTPException(status_code=403, detail='invalid csrf token')
    g = get_job(job_id)
    if not g: raise HTTPException(status_code=404, detail='job not found')
    return g

    cur.execute('''CREATE TABLE IF NOT EXISTS refresh_tokens (token TEXT PRIMARY KEY, username TEXT, expires DATETIME)''')
    conn.commit()
    conn.close()

@app.post('/auth/refresh')
async def refresh_token(body: dict):
    token = body.get('refresh_token')
    if not token:
        raise HTTPException(status_code=400, detail='Missing refresh token')

    conn = None
    try:
        conn = sqlite3.connect(USER_DB)
        cur = conn.cursor()
        cur.execute('SELECT username FROM refresh_tokens WHERE token=?', (token,))
        refresh_row = cur.fetchone()
        if not refresh_row:
            raise HTTPException(status_code=401, detail='Invalid refresh token')

        username = refresh_row[0]
        cur.execute('SELECT role FROM users WHERE username=?', (username,))
        user_row = cur.fetchone()
        role = user_row[0] if user_row else 'developer' # Default role if user not found
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if conn:
            conn.close()

    new_token = create_access_token({'sub': username, 'role': role})
    return {'access_token': new_token, 'token_type': 'bearer'}

from fastapi.responses import FileResponse

@app.get('/artifacts')
async def list_artifacts(user = Depends(get_current_user), x_csrf_token: str = Header(None)):
    require_role(user, ['developer','admin'])
    if not x_csrf_token or not validate_csrf_for_user(user.get('username'), x_csrf_token):
        raise HTTPException(status_code=403, detail='invalid csrf token')
    out = []
    d = os.getenv('ARTIFACTS_DIR','./artifacts')
    if not os.path.exists(d): return {'artifacts': out}
    for root, dirs, files in os.walk(d):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), d)
            out.append({'name': rel, 'path': rel})
    return {'artifacts': out}

@app.get('/artifacts/download')
async def download_artifact(name: str, user = Depends(get_current_user), x_csrf_token: str = Header(None)):
    require_role(user, ['developer','admin'])
    if not x_csrf_token or not validate_csrf_for_user(user.get('username'), x_csrf_token):
        raise HTTPException(status_code=403, detail='invalid csrf token')
    d = os.getenv('ARTIFACTS_DIR','./artifacts')
    safe_path = os.path.normpath(os.path.join(d, name))
    if not safe_path.startswith(os.path.abspath(d)):
        raise HTTPException(status_code=400, detail='Invalid path')
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail='Not found')
    return FileResponse(safe_path, filename=os.path.basename(name))


@app.websocket('/ws/stream')
async def websocket_stream(websocket: WebSocket, provider: str = 'openrouter', token: str = None):
    await websocket.accept()
    # very light auth check
    try:
        if token is None:
            raise WebSocketDisconnect(code=1008)
        # token validation
        from jose import jwt
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        await websocket.close(code=1008)
        return
    # import provider adapter
    import importlib
    try:
        mod = importlib.import_module(f'providers.{provider}_adapter')
    except Exception:
        await websocket.send_json({'error':'provider_not_found'})
        await websocket.close()
        return
    try:
        # stream chunks
        if hasattr(mod, 'generate_stream_with_seq'):
            for item in mod.generate_stream_with_seq(websocket.scope.get('query_string','') or ''):
                await websocket.send_json(item)
                await asyncio.sleep(0.02)
        else:
            for chunk in mod.generate_stream(websocket.scope.get('query_string','') or ''):
                await websocket.send_json({'seq':None,'chunk':chunk})
                await asyncio.sleep(0.02)
    except WebSocketDisconnect:
        return
    except Exception as e:
        try: await websocket.send_json({'error':str(e)})
        except: pass
    await websocket.close()



def create_user_pg(username, hashed_password, role='developer'):
    import psycopg2
    conn = psycopg2.connect(AGENT_USER_DB_URL); cur = conn.cursor()
    cur.execute('INSERT INTO users (username, hashed_password, role) VALUES (%s,%s,%s)', (username, hashed_password, role))
    conn.commit(); conn.close()

def store_reset_token(username, token, expires):
    # This function is not async and is called from an async context, which is not ideal.
    # For now, just making the DB connection safe.
    conn = None
    try:
        if USE_PG_USERS:
            import psycopg2
            conn = psycopg2.connect(AGENT_USER_DB_URL)
            cur = conn.cursor()
            cur.execute('INSERT INTO password_resets (token, username, expires) VALUES (%s,%s,%s)', (token, username, expires))
        else:
            conn = sqlite3.connect(USER_DB)
            cur = conn.cursor()
            cur.execute('INSERT INTO password_resets(token,username,expires) VALUES(?,?,?)', (token, username, expires))
        conn.commit()
    except (sqlite3.Error, psycopg2.Error) as e:
        logging.error(f"Failed to store reset token for user {username}: {e}")
    finally:
        if conn:
            conn.close()

def verify_reset_token(token):
    import datetime
    conn = None
    try:
        if USE_PG_USERS:
            import psycopg2
            conn = psycopg2.connect(AGENT_USER_DB_URL)
            cur = conn.cursor()
            cur.execute('SELECT username, expires FROM password_resets WHERE token=%s', (token,))
            row = cur.fetchone()
            if not row: return None
            uname, exp = row[0], row[1]
            if exp < datetime.datetime.utcnow(): return None
            return uname
        else:
            conn = sqlite3.connect(USER_DB)
            cur = conn.cursor()
            cur.execute('SELECT username, expires FROM password_resets WHERE token=?', (token,))
            row = cur.fetchone()
            if not row: return None
            uname, exp = row[0], row[1]
            if datetime.datetime.fromisoformat(exp) < datetime.datetime.utcnow(): return None
            return uname
    except (sqlite3.Error, psycopg2.Error) as e:
        logging.error(f"Failed to verify reset token: {e}")
        return None
    finally:
        if conn:
            conn.close()


@app.post('/auth/request_reset')
async def request_reset(body: dict):
    username = body.get('username')
    if not username: raise HTTPException(status_code=400, detail='missing')
    token = str(uuid.uuid4())
    import datetime
    expires = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat()
    store_reset_token(username, token, expires)
    # In production, send email; here return token for convenience
    return {'reset_token': token, 'expires': expires}

@app.post('/auth/reset')
async def reset_password(body: dict):
    token = body.get('token'); newpw = body.get('password')
    if not token or not newpw: raise HTTPException(status_code=400, detail='missing')
    uname = verify_reset_token(token)
    if not uname: raise HTTPException(status_code=400, detail='invalid or expired')

    h = get_password_hash(newpw)
    conn = None
    try:
        if USE_PG_USERS:
            import psycopg2
            conn = psycopg2.connect(AGENT_USER_DB_URL)
            cur = conn.cursor()
            cur.execute('UPDATE users SET hashed_password=%s WHERE username=%s', (h, uname))
        else:
            conn = sqlite3.connect(USER_DB)
            cur = conn.cursor()
            cur.execute('UPDATE users SET hashed_password=? WHERE username=?', (h, uname))
        conn.commit()
    except (sqlite3.Error, psycopg2.Error) as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if conn:
            conn.close()

    return {'ok': True}


@app.get('/auth/validate')
async def validate_token(authorization: str = Header(None)):
    if not authorization: raise HTTPException(status_code=401, detail='Missing token')
    token = authorization.split()[-1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {'valid': True, 'sub': payload.get('sub'), 'role': payload.get('role')}
    except JWTError:
        raise HTTPException(status_code=401, detail='Invalid token')


# CSRF token helpers
def init_csrf_table():
    conn = None
    try:
        conn = sqlite3.connect(USER_DB)
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS csrf_tokens (token TEXT PRIMARY KEY, username TEXT, expires TEXT)''')
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to create csrf_tokens table: {e}")
    finally:
        if conn:
            conn.close()

@app.post('/auth/csrf')
async def issue_csrf(user = Depends(get_current_user)):
    import uuid, datetime
    token = str(uuid.uuid4())
    expires = (datetime.datetime.utcnow() + datetime.timedelta(minutes=30)).isoformat()
    conn = None
    try:
        conn = sqlite3.connect(USER_DB)
        cur = conn.cursor()
        cur.execute('INSERT INTO csrf_tokens(token,username,expires) VALUES(?,?,?)', (token, user.get('username'), expires))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to issue CSRF token for user {user.get('username')}: {e}")
    finally:
        if conn:
            conn.close()
    return {'csrf_token': token, 'expires': expires}

def validate_csrf_for_user(username, token):
    conn = None
    try:
        conn = sqlite3.connect(USER_DB)
        cur = conn.cursor()
        cur.execute('SELECT username,expires FROM csrf_tokens WHERE token=?', (token,))
        row = cur.fetchone()
        if not row: return False
        import datetime
        if row[0] != username: return False
        if datetime.datetime.fromisoformat(row[1]) < datetime.datetime.utcnow(): return False
        return True
    except (sqlite3.Error, TypeError) as e:
        logging.error(f"CSRF validation failed for user {username}: {e}")
        return False
    finally:
        if conn:
            conn.close()



@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
