import asyncio
import logging
import os
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.config import BOT_TOKEN, UPLOAD_DIR, NGROK_AUTHTOKEN
from backend.mimo_api import list_sessions, get_messages, send_message, create_session
from backend.monitor import get_status

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mimo-tg")

_term_proc = None
_term_output = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task = None
    if BOT_TOKEN:
        from backend.bot import start_bot, stop_bot
        bot_task = asyncio.create_task(start_bot())
        log.info("Bot started")
    yield
    if bot_task:
        bot_task.cancel()


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
async def index():
    return FileResponse(os.path.join(frontend, "index.html"))


@app.get("/api/sessions")
async def api_sessions():
    return await list_sessions()


@app.post("/api/sessions")
async def api_create_session():
    sid = await create_session()
    if sid:
        return {"id": sid}
    raise HTTPException(502, "Failed to create session")


@app.get("/api/sessions/{sid}/messages")
async def api_messages(sid: str):
    return {"messages": await get_messages(sid)}


@app.post("/api/chat")
async def api_chat(body: dict):
    sid = body.get("session_id", "")
    text = body.get("text", "")
    if not text:
        raise HTTPException(400, "Empty message")
    if not sid:
        sid = await create_session()
    if not sid:
        raise HTTPException(502, "No session")
    status = await send_message(sid, text)
    return {"ok": status in (200, 201), "session_id": sid}


@app.get("/api/status")
async def api_status():
    return get_status()


@app.post("/api/files/upload")
async def api_upload(file: UploadFile = File(...)):
    data = await file.read()
    path = os.path.join(UPLOAD_DIR, file.filename)
    with open(path, "wb") as f:
        f.write(data)
    return {"ok": True, "name": file.filename, "size": len(data)}


@app.get("/api/files")
async def api_files():
    files = []
    if os.path.exists(UPLOAD_DIR):
        for f in os.listdir(UPLOAD_DIR):
            files.append({"name": f, "size": os.path.getsize(os.path.join(UPLOAD_DIR, f))})
    return {"files": files}


@app.delete("/api/files/{name}")
async def api_delete_file(name: str):
    path = os.path.join(UPLOAD_DIR, name)
    if os.path.exists(path):
        os.remove(path)
    return {"ok": True}


@app.post("/api/terminal/start")
async def api_term_start(body: dict):
    global _term_proc, _term_output
    cmd = body.get("command", "")
    if not cmd:
        raise HTTPException(400, "No command")
    if _term_proc and _term_proc.poll() is None:
        _term_proc.kill()
    _term_output = [{"type": "info", "text": f"$ {cmd}"}]
    try:
        _term_proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
    except Exception as e:
        _term_output.append({"type": "stderr", "text": str(e)})
        return {"ok": False}
    asyncio.create_task(_read_term())
    return {"ok": True}


async def _read_term():
    global _term_proc
    while _term_proc and _term_proc.poll() is None:
        line = _term_proc.stdout.readline()
        if line:
            _term_output.append({"type": "stdout", "text": line.rstrip("\n")})
        else:
            await asyncio.sleep(0.1)
    if _term_proc:
        _term_output.append({"type": "info", "text": f"[Exit: {_term_proc.returncode}]"})
    else:
        _term_output.append({"type": "info", "text": "[Process killed]"})


@app.post("/api/terminal/stop")
async def api_term_stop():
    global _term_proc
    if _term_proc and _term_proc.poll() is None:
        _term_proc.kill()
    return {"ok": True}


@app.get("/api/terminal/output")
async def api_term_output():
    return {"output": _term_output[-200:], "running": _term_proc is not None and _term_proc.poll() is None}


app.mount("/static", StaticFiles(directory=frontend), name="static")
