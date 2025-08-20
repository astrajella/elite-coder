import os, jwt
from fastapi import Header, HTTPException, Depends

ALGO = 'HS256'

def require_secret():
    secret = os.getenv('JWT_SECRET')
    if not secret:
        raise RuntimeError('JWT_SECRET required')
    return secret

def auth_dependency(authorization: str = Header(None)):
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='Missing bearer token')
    token = authorization.split(' ',1)[1]
    try:
        decoded = jwt.decode(token, require_secret(), algorithms=[ALGO])
        return decoded
    except Exception as e:
        raise HTTPException(status_code=401, detail='Invalid token: '+str(e))
