import asyncio, os, subprocess, time, logging, json
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
import aiohttp, psutil
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MIMO_URL = os.getenv("MIMO_URL", "http://127.0.0.1:7860")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
FRONTEND = os.path.join(os.path.dirname(__file__), "frontend")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mimo")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_term_proc = None
_term_output = []
_tunnel_url = None


# ─── SSE Proxy ───
@app.get("/api/events")
async def sse_proxy():
    async def gen():
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{MIMO_URL}/event") as r:
                    async for line in r.content:
                        decoded = line.decode("utf-8", errors="replace")
                        if decoded.strip():
                            yield decoded
        except Exception as e:
            log.error(f"SSE error: {e}")
            yield f'data: {{"type":"error","properties":{{"message":"{str(e)}"}}}}\n\n'
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ─── Startup ───
@app.on_event("startup")
async def startup():
    asyncio.create_task(_start_tunnel())
    if BOT_TOKEN:
        asyncio.create_task(_run_bot())
    asyncio.create_task(_watchdog_mimo())
    log.info("Started")


async def _start_tunnel():
    global _tunnel_url
    # Kill old ngrok
    subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe"], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)
    await asyncio.sleep(2)

    # Try cloudflared first
    cf = r"C:\Users\123\cloudflared.exe"
    if os.path.exists(cf):
        try:
            proc = await asyncio.create_subprocess_exec(
                cf, "tunnel", "--url", "http://localhost:8765",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            async for line in proc.stdout:
                text = line.decode("utf-8", errors="replace")
                if "trycloudflare.com" in text:
                    url = [w for w in text.split() if "trycloudflare.com" in w][0].strip()
                    _tunnel_url = "https://" + url.split("//")[-1] if "://" in url else url
                    log.info(f"Cloudflare tunnel: {_tunnel_url}")
                    return
        except Exception as e:
            log.error(f"Cloudflared failed: {e}")

    # Fallback: ngrok
    try:
        from pyngrok import ngrok, conf
        token = os.getenv("NGROK_AUTHTOKEN", "")
        if token:
            conf.get_default().auth_token = token
            t = ngrok.connect(8765, "http", bind_tls=True)
            _tunnel_url = t.public_url
            log.info(f"Ngrok tunnel: {_tunnel_url}")
    except Exception as e:
        log.error(f"Ngrok failed: {e}")
        _tunnel_url = None


async def _watchdog_mimo():
    while True:
        await asyncio.sleep(30)
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{MIMO_URL}/session", timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status != 200:
                        raise Exception("bad")
        except Exception:
            log.warning("mimo serve dead, restarting...")
            try:
                subprocess.Popen(["cmd", "/c", "start", "/min", "cmd", "/c",
                    r"C:\Users\123\AppData\Roaming\npm\mimo.cmd", "serve", "--port", "7860"])
            except Exception as e:
                log.error(f"mimo restart failed: {e}")
            await asyncio.sleep(5)


ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))


async def _run_bot():
    from aiogram import Bot, Dispatcher, F
    from aiogram.types import Message, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup

    for i in range(60):
        if _tunnel_url and _tunnel_url.startswith("https"):
            break
        await asyncio.sleep(2)
    if not _tunnel_url or not _tunnel_url.startswith("https"):
        log.error("No HTTPS URL, bot not started")
        return

    async def cmd_start(message: Message):
        if ALLOWED_USER_ID and message.from_user.id != ALLOWED_USER_ID:
            await message.answer("Доступ запрещён.")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть MiMo App", web_app=WebAppInfo(url=_tunnel_url))]
        ])
        await message.answer("<b>MiMo Code</b>\nНажмите чтобы открыть Mini App.",
                             reply_markup=kb, parse_mode="HTML")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(cmd_start, F.text == "/start")
    log.info(f"Bot started: {_tunnel_url}")
    await dp.start_polling(bot)


# ─── API ───
@app.get("/")
async def index():
    resp = FileResponse(os.path.join(FRONTEND, "index.html"))
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/health")
async def health():
    return {"status": "ok", "tunnel": _tunnel_url}


@app.get("/api/sessions")
async def get_sessions():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{MIMO_URL}/session", timeout=aiohttp.ClientTimeout(total=5)) as r:
                data = await r.json()
        result = []
        for ses in data:
            title = ses.get("title", "")
            if not title or "checkpoint" in title.lower() or "parentID" in ses:
                continue
            tokens = 0
            try:
                async with aiohttp.ClientSession() as s2:
                    async with s2.get(f"{MIMO_URL}/session/{ses['id']}/message", timeout=aiohttp.ClientTimeout(total=3)) as r2:
                        msgs = await r2.json()
                for m in msgs:
                    t = m.get("info", {}).get("tokens", {})
                    tokens += (t.get("total", 0) or 0)
            except Exception:
                pass
            result.append({"id": ses["id"], "title": title[:60],
                           "created": ses.get("time", {}).get("created", 0), "tokens": tokens})
        result.sort(key=lambda x: x["created"], reverse=True)
        return {"sessions": result[:30]}
    except Exception:
        return {"sessions": []}


@app.get("/api/sessions/{sid}/messages")
async def get_messages(sid: str):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{MIMO_URL}/session/{sid}/message", timeout=aiohttp.ClientTimeout(total=5)) as r:
                data = await r.json()
        messages = []
        total_tokens = 0
        for msg in data:
            role = msg.get("info", {}).get("role", "")
            tokens = msg.get("info", {}).get("tokens", {})
            total_tokens += tokens.get("total", 0) or 0
            if role not in ("user", "assistant"):
                continue
            parts = msg.get("parts", [])
            text_parts = []
            tool_calls = []
            for p in parts:
                if p.get("type") == "text":
                    text_parts.append(p.get("text", ""))
                elif p.get("type") == "tool":
                    tool_calls.append({"tool": p.get("tool", ""), "status": p.get("state", {}).get("status", "")})
            if text_parts or tool_calls:
                messages.append({"role": role, "text": "\n".join(text_parts), "tools": tool_calls})
        return {"messages": messages, "tokens": total_tokens}
    except Exception:
        return {"messages": [], "tokens": 0}


@app.post("/api/chat")
async def chat(body: dict):
    try:
        sid = body.get("session_id", "")
        text = body.get("text", "")
        if not text:
            raise HTTPException(400, "Empty")
        if not sid:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{MIMO_URL}/session", timeout=aiohttp.ClientTimeout(total=5)) as r:
                    d = await r.json()
                    sid = d.get("id", "")
        if not sid:
            raise HTTPException(502, "No session")
        async with aiohttp.ClientSession() as s:
            await s.post(f"{MIMO_URL}/session/{sid}/prompt_async",
                        json={"parts": [{"type": "text", "text": text}]},
                        timeout=aiohttp.ClientTimeout(total=10))
        return {"ok": True, "session_id": sid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/status")
async def status():
    try:
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        gt = gl = vp = vu = vt = 0.0
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
                               "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                p = r.stdout.strip().split(", ")
                gt, gl, vu, vt = float(p[0]), float(p[1]), float(p[2]), float(p[3])
                vp = vu / vt * 100 if vt > 0 else 0
        except Exception:
            pass
        return {"cpu": cpu, "ram_pct": mem.percent,
                "ram_used": round(mem.used / 1073741824, 1), "ram_total": round(mem.total / 1073741824, 1),
                "gpu_temp": gt, "gpu_load": round(gl, 1),
                "vram_pct": round(vp, 1), "vram_used": round(vu), "vram_total": round(vt)}
    except Exception:
        return {"cpu": 0, "ram_pct": 0, "ram_used": 0, "ram_total": 0, "gpu_temp": 0, "gpu_load": 0, "vram_pct": 0, "vram_used": 0, "vram_total": 0}


@app.get("/api/terminal/output")
async def term_output():
    return {"output": _term_output[-200:], "running": _term_proc is not None and _term_proc.poll() is None}


@app.post("/api/terminal/start")
async def term_start(body: dict):
    global _term_proc, _term_output
    cmd = body.get("command", "")
    if not cmd:
        raise HTTPException(400, "No command")
    if _term_proc and _term_proc.poll() is None:
        _term_proc.kill()
    _term_output = [{"type": "info", "text": f"$ {cmd}"}]
    try:
        _term_proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
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
    if _term_proc:
        _term_output.append({"type": "info", "text": f"[Exit: {_term_proc.returncode}]"})
    else:
        _term_output.append({"type": "info", "text": "[Killed]"})


@app.post("/api/terminal/stop")
async def term_stop():
    global _term_proc
    if _term_proc and _term_proc.poll() is None:
        _term_proc.kill()
    return {"ok": True}


@app.get("/api/files")
async def list_files():
    files = []
    for f in os.listdir(UPLOAD_DIR):
        files.append({"name": f, "size": os.path.getsize(os.path.join(UPLOAD_DIR, f))})
    return {"files": files}


@app.post("/api/files/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    with open(os.path.join(UPLOAD_DIR, file.filename), "wb") as f:
        f.write(data)
    return {"ok": True, "name": file.filename, "size": len(data)}


@app.get("/api/files/raw/{name}")
async def serve_file(name: str):
    path = os.path.join(UPLOAD_DIR, name)
    if not os.path.exists(path):
        raise HTTPException(404)
    import mimetypes
    return FileResponse(path, media_type=mimetypes.guess_type(name)[0] or "application/octet-stream")


@app.delete("/api/files/{name}")
async def delete_file(name: str):
    p = os.path.join(UPLOAD_DIR, name)
    if os.path.exists(p):
        os.remove(p)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
