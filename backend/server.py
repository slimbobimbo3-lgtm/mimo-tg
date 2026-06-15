import asyncio, os, subprocess, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import aiohttp, psutil
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MIMO_URL = os.getenv("MIMO_URL", "http://127.0.0.1:7860")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

log = logging.getLogger("mimo")
logging.basicConfig(level=logging.INFO)

_term_proc = None
_term_out = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    if BOT_TOKEN:
        asyncio.create_task(_run_bot())
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FE = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
async def index():
    return FileResponse(os.path.join(FE, "index.html"))


# --- Sessions ---
@app.get("/api/sessions")
async def sessions():
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{MIMO_URL}/session") as r:
            data = await r.json()
    out = []
    for x in data:
        out.append({"id": x["id"], "title": x.get("title", "Untitled"), "created": x.get("time", {}).get("created", 0)})
    out.sort(key=lambda x: x["created"], reverse=True)
    return {"sessions": out}


@app.post("/api/sessions")
async def new_session():
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{MIMO_URL}/session") as r:
            if r.status in (200, 201):
                d = await r.json()
                return {"id": d.get("id")}
    raise HTTPException(502, "fail")


@app.get("/api/sessions/{sid}/messages")
async def messages(sid: str):
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{MIMO_URL}/session/{sid}/message") as r:
            data = await r.json()
    out = []
    for m in data:
        role = m.get("info", {}).get("role", "")
        if role not in ("user", "assistant"):
            continue
        texts = [p.get("text", "") for p in m.get("parts", []) if p.get("type") == "text"]
        if texts:
            out.append({"role": role, "text": "\n".join(texts)})
    return {"messages": out}


@app.post("/api/chat")
async def chat(body: dict):
    text = body.get("text", "")
    sid = body.get("session_id", "")
    if not text:
        raise HTTPException(400, "empty")
    if not sid:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{MIMO_URL}/session") as r:
                d = await r.json()
                sid = d.get("id", "")
    if not sid:
        raise HTTPException(502, "no session")
    async with aiohttp.ClientSession() as s:
        await s.post(f"{MIMO_URL}/session/{sid}/prompt_async", json={"parts": [{"type": "text", "text": text}]})
    return {"ok": True, "session_id": sid}


# --- Status ---
@app.get("/api/status")
async def status():
    cpu = psutil.cpu_percent(interval=0.2)
    mem = psutil.virtual_memory()
    gt = gl = vp = vu = vt = 0.0
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            p = r.stdout.strip().split(", ")
            gt, gl, vu, vt = float(p[0]), float(p[1]), float(p[2]), float(p[3])
            vp = vu / vt * 100 if vt > 0 else 0
    except Exception:
        pass
    return {"cpu": cpu, "ram_pct": mem.percent, "ram_used": round(mem.used / 1073741824, 1), "ram_total": round(mem.total / 1073741824, 1), "gpu_temp": gt, "gpu_load": round(gl, 1), "vram_pct": round(vp, 1), "vram_used": round(vu), "vram_total": round(vt)}


# --- Terminal ---
@app.post("/api/terminal/start")
async def term_start(body: dict):
    global _term_proc, _term_out
    cmd = body.get("command", "")
    if not cmd:
        raise HTTPException(400, "no cmd")
    if _term_proc and _term_proc.poll() is None:
        _term_proc.kill()
    _term_out = [{"type": "info", "text": f"$ {cmd}"}]
    try:
        _term_proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    except Exception as e:
        _term_out.append({"type": "stderr", "text": str(e)})
        return {"ok": False}
    asyncio.create_task(_read_term())
    return {"ok": True}


async def _read_term():
    global _term_proc
    while _term_proc and _term_proc.poll() is None:
        line = await asyncio.get_event_loop().run_in_executor(None, _term_proc.stdout.readline)
        if line:
            _term_out.append({"type": "stdout", "text": line.rstrip("\n")})
    if _term_proc:
        _term_out.append({"type": "info", "text": f"[Exit: {_term_proc.returncode}]"})
    else:
        _term_out.append({"type": "info", "text": "[Killed]"})


@app.post("/api/terminal/stop")
async def term_stop():
    global _term_proc
    if _term_proc and _term_proc.poll() is None:
        _term_proc.kill()
    return {"ok": True}


@app.get("/api/terminal/output")
async def term_output():
    return {"output": _term_out[-200:], "running": _term_proc is not None and _term_proc.poll() is None}


# --- Files ---
@app.get("/api/files")
async def files():
    out = []
    for f in os.listdir(UPLOAD_DIR):
        out.append({"name": f, "size": os.path.getsize(os.path.join(UPLOAD_DIR, f))})
    return {"files": out}


@app.post("/api/files/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    with open(os.path.join(UPLOAD_DIR, file.filename), "wb") as f:
        f.write(data)
    return {"ok": True, "name": file.filename, "size": len(data)}


@app.delete("/api/files/{name}")
async def del_file(name: str):
    p = os.path.join(UPLOAD_DIR, name)
    if os.path.exists(p):
        os.remove(p)
    return {"ok": True}


# --- Bot ---
async def _run_bot():
    from aiogram import Bot, Dispatcher, F
    from aiogram.types import Message, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
    from pyngrok import ngrok, conf as ngconf

    conf.get_default().auth_token = os.getenv("NGROK_AUTHTOKEN", "")
    try:
        tunnel = ngrok.connect(8765, "http", bind_tls=True)
        url = tunnel.public_url
        log.info(f"Tunnel: {url}")
    except Exception as e:
        log.error(f"Tunnel failed: {e}")
        url = "http://localhost:8765"

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(F.text == "/start")
    async def cmd_start(message: Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть MiMo App", web_app=WebAppInfo(url=url))]])
        await message.answer("<b>MiMo Code</b> — Remote Assistant\n\nНажмите кнопку чтобы открыть Mini App.", reply_markup=kb, parse_mode="HTML")

    asyncio.create_task(dp.start_polling(bot))
    await asyncio.Event().wait()


app.mount("/static", StaticFiles(directory=FE), name="static")
