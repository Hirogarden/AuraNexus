from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from typing import List

app = FastAPI()
KCPP_URL = os.getenv('KCPP_URL','http://127.0.0.1:5001')
ANYLLM_URL = os.getenv('ANYLLM_URL','http://127.0.0.1:8000')

# Allow local UI (Electron) to access these endpoints
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
async def root():
    return {"status":"Aura API running"}


@app.post('/v1/chat/completions')
async def chat_proxy(req: Request):
    body = await req.json()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{KCPP_URL}/v1/chat/completions", json=body, timeout=120.0)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
    return r.json()


@app.post('/rag/ingest')
async def rag_ingest(req: Request):
    body = await req.json()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{ANYLLM_URL}/api/ingest", json=body, timeout=120.0)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail=r.text)
    return {"status":"ok"}


# Simple log viewer endpoints
LOGS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'logs'))


def _safe_log_path(name: str) -> str:
    if '..' in name or name.startswith('/') or name.startswith('\\'):
        raise HTTPException(status_code=400, detail='Invalid log name')
    path = os.path.normpath(os.path.join(LOGS_DIR, name))
    if not path.startswith(os.path.abspath(LOGS_DIR)):
        raise HTTPException(status_code=400, detail='Invalid log name')
    return path


@app.get('/logs', response_model=List[str])
async def list_logs():
    if not os.path.exists(LOGS_DIR):
        return []
    files = [f for f in os.listdir(LOGS_DIR) if os.path.isfile(os.path.join(LOGS_DIR, f))]
    files.sort()
    return files


def tail_file(path: str, lines: int = 200) -> str:
    # Efficient tail: read blocks from end until enough lines collected
    try:
        with open(path, 'rb') as f:
            avg_line_length = 200
            to_read = lines * avg_line_length
            try:
                f.seek(-to_read, os.SEEK_END)
            except OSError:
                f.seek(0)
            data = f.read().decode('utf-8', errors='replace')
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='Log not found')
    arr = data.splitlines()
    return '\n'.join(arr[-lines:])


@app.get('/logs/{name}')
async def get_log(name: str, lines: int = 200):
    path = _safe_log_path(name)
    content = tail_file(path, lines=lines)
    return Response(content, media_type='text/plain')
