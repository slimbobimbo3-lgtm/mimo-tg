import asyncio, os, subprocess, time, logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import aiohttp, psutil
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MIMO_URL = os.getenv("MIMO_URL", "http://127.0.0.1:7860")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
FRONTEND = os.path.join(os.path.dirname(__file__), "frontend")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mimo")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    setup_ngrok()
    if BOT_TOKEN:
        asyncio.create_task(_run_bot())
        log.info("Bot polling started")
    asyncio.create_task(_watchdog_ngrok())
    asyncio.create_task(_watchdog_mimo())
    log.info("Watchdogs started")


@app.get("/health")
async def health():
    return {"status": "ok"}

_term_proc = None
_term_output = []
_tunnel_url = None


def setup_ngrok():
    global _tunnel_url
    token = os.getenv("NGROK_AUTHTOKEN", "")
    if not token:
        _tunnel_url = "http://localhost:8765"
        log.info("Ngrok token not set, using local URL: http://localhost:8765")
        return
    try:
        subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe"], capture_output=True)
    except Exception:
        pass
    try:
        from pyngrok import ngrok, conf
        conf.get_default().auth_token = token
        t = ngrok.connect(8765, "http", bind_tls=True)
        _tunnel_url = t.public_url
        log.info(f"Tunnel: {_tunnel_url}")
    except Exception as e:
        log.error(f"Ngrok failed: {e}")


async def _watchdog_ngrok():
    while True:
        await asyncio.sleep(300)
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("http://127.0.0.1:4040/api/tunnels", timeout=aiohttp.ClientTimeout(total=5)) as r:
                    data = await r.json()
                    tunnels = data.get("tunnels", [])
                    if not tunnels:
                        log.warning("Ngrok: no tunnels, reconnecting")
                        setup_ngrok()
        except Exception:
            log.warning("Ngrok: dead, reconnecting")
            setup_ngrok()


async def _watchdog_mimo():
    while True:
        await asyncio.sleep(30)
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{MIMO_URL}/session", timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status != 200:
                        raise Exception("bad status")
        except Exception:
            log.warning("mimo serve: dead, restarting...")
            try:
                subprocess.Popen(
                    ["cmd", "/c", "start", "/min", "MimoServe", "cmd", "/c",
                     r"C:\Users\123\AppData\Roaming\npm\mimo.cmd", "serve", "--port", "7860"],
                    shell=False
                )
            except Exception as e:
                log.error(f"mimo serve restart failed: {e}")
            await asyncio.sleep(5)


ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))


async def _run_bot():
    from aiogram import Bot, Dispatcher, F
    from aiogram.types import Message, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup

    for i in range(30):
        if _tunnel_url:
            break
        log.info(f"Waiting for ngrok... ({i+1}/30)")
        await asyncio.sleep(2)

    if not _tunnel_url:
        log.error("No tunnel URL after 60s, bot not started")
        return

    async def cmd_start(message: Message):
        if ALLOWED_USER_ID and message.from_user.id != ALLOWED_USER_ID:
            await message.answer("Доступ запрещён.")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть MiMo App", web_app=WebAppInfo(url=_tunnel_url))]
        ])
        await message.answer(
            "<b>MiMo Code</b>\n\n"
            "Команды:\n"
            "/start — открыть Mini App\n"
            "/save [описание] — сохранить версию\n"
            "/versions — список сохранённых версий\n"
            "/restore [номер] — откатиться на версию",
            reply_markup=kb, parse_mode="HTML"
        )

    async def cmd_save(message: Message):
        if ALLOWED_USER_ID and message.from_user.id != ALLOWED_USER_ID:
            return
        desc = message.text.replace("/save", "").strip() or "Без описания"
        versions_dir = os.path.join(os.path.dirname(__file__), "versions")
        os.makedirs(versions_dir, exist_ok=True)
        files_to_save = ["server.py", "frontend/index.html", ".env"]
        ver_num = len([f for f in os.listdir(versions_dir) if f.startswith("v")]) + 1
        ver_dir = os.path.join(versions_dir, f"v{ver_num}")
        os.makedirs(ver_dir, exist_ok=True)
        saved = []
        for f in files_to_save:
            src = os.path.join(os.path.dirname(__file__), f)
            if os.path.exists(src):
                with open(src, "r", encoding="utf-8") as sf:
                    content = sf.read()
                with open(os.path.join(ver_dir, os.path.basename(f)), "w", encoding="utf-8") as df:
                    df.write(content)
                saved.append(os.path.basename(f))
        with open(os.path.join(ver_dir, "README.txt"), "w", encoding="utf-8") as rf:
            rf.write(f"Версия {ver_num}\nОписание: {desc}\nДата: {time.strftime('%Y-%m-%d %H:%M')}\nФайлы: {', '.join(saved)}")
        await message.answer(f"✅ Сохранена версия <b>v{ver_num}</b>\n{desc}\n\nФайлы: {', '.join(saved)}", parse_mode="HTML")

    async def cmd_versions(message: Message):
        if ALLOWED_USER_ID and message.from_user.id != ALLOWED_USER_ID:
            return
        versions_dir = os.path.join(os.path.dirname(__file__), "versions")
        if not os.path.exists(versions_dir):
            await message.answer("Нет сохранённых версий.")
            return
        vers = sorted([d for d in os.listdir(versions_dir) if d.startswith("v")], key=lambda x: int(x[1:]))
        if not vers:
            await message.answer("Нет сохранённых версий.")
            return
        lines = ["<b>Сохранённые версии:</b>\n"]
        for v in vers[-10:]:
            readme = os.path.join(versions_dir, v, "README.txt")
            desc = ""
            if os.path.exists(readme):
                with open(readme, "r", encoding="utf-8") as f:
                    lines_file = f.readlines()
                    if len(lines_file) > 1:
                        desc = lines_file[1].replace("Описание: ", "").strip()
            lines.append(f"/restore_{v[1:]} — {desc}")
        await message.answer("\n".join(lines), parse_mode="HTML")

    async def cmd_restore(message: Message):
        if ALLOWED_USER_ID and message.from_user.id != ALLOWED_USER_ID:
            return
        ver_num = message.text.replace("/restore_", "").strip()
        if not ver_num.isdigit():
            await message.answer("Используйте /restore_номер (например /restore_3)")
            return
        versions_dir = os.path.join(os.path.dirname(__file__), "versions")
        ver_dir = os.path.join(versions_dir, f"v{ver_num}")
        if not os.path.exists(ver_dir):
            await message.answer(f"Версия v{ver_num} не найдена.")
            return
        restored = []
        for f in os.listdir(ver_dir):
            if f == "README.txt":
                continue
            src = os.path.join(ver_dir, f)
            if f == ".env":
                dst = os.path.join(os.path.dirname(__file__), ".env")
            elif f == "index.html":
                dst = os.path.join(os.path.dirname(__file__), "frontend", f)
            else:
                dst = os.path.join(os.path.dirname(__file__), f)
            with open(src, "r", encoding="utf-8") as sf:
                content = sf.read()
            with open(dst, "w", encoding="utf-8") as df:
                df.write(content)
            restored.append(f)
        await message.answer(f"✅ Версия <b>v{ver_num}</b> восстановлена: {', '.join(restored)}\nПерезапустите сервер.", parse_mode="HTML")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(cmd_start, F.text == "/start")
    dp.message.register(cmd_save, F.text.startswith("/save"))
    dp.message.register(cmd_versions, F.text == "/versions")
    dp.message.register(cmd_restore, F.text.startswith("/restore_"))
    log.info(f"Bot started with URL: {_tunnel_url}")
    await dp.start_polling(bot)


@app.get("/")
async def index():
    resp = FileResponse(os.path.join(FRONTEND, "index.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


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
            result.append({
                "id": ses["id"],
                "title": title[:60],
                "created": ses.get("time", {}).get("created", 0),
                "tokens": tokens,
            })
        result.sort(key=lambda x: x["created"], reverse=True)
        return {"sessions": result[:30]}
    except Exception as e:
        log.error(f"Sessions error: {e}")
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
            text_parts = []
            for part in msg.get("parts", []):
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            if text_parts:
                messages.append({"role": role, "text": "\n".join(text_parts)})
        return {"messages": messages, "tokens": total_tokens}
    except Exception as e:
        log.error(f"Messages error: {e}")
        return {"messages": [], "tokens": 0}


@app.delete("/api/sessions/{sid}")
async def delete_session(sid: str):
    try:
        async with aiohttp.ClientSession() as s:
            await s.delete(f"{MIMO_URL}/session/{sid}", timeout=aiohttp.ClientTimeout(total=5))
        return {"ok": True}
    except Exception:
        return {"ok": False}


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
                    if r.status in (200, 201):
                        d = await r.json()
                        sid = d.get("id", "")
        if not sid:
            raise HTTPException(502, "No session")
        payload = {"parts": [{"type": "text", "text": text}]}
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{MIMO_URL}/session/{sid}/prompt_async", json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
                return {"ok": r.status in (200, 201), "session_id": sid}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Chat error: {e}")
        raise HTTPException(500, str(e))


@app.get("/api/status")
async def status():
    try:
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        gpu_temp = gpu_load = vram_pct = vram_used = vram_total = 0.0
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3
            )
            if r.returncode == 0:
                p = r.stdout.strip().split(", ")
                gpu_temp, gpu_load = float(p[0]), float(p[1])
                vram_used, vram_total = float(p[2]), float(p[3])
                vram_pct = (vram_used / vram_total * 100) if vram_total > 0 else 0
        except Exception:
            pass
        return {
            "cpu": cpu, "ram_pct": mem.percent,
            "ram_used": round(mem.used / 1073741824, 1),
            "ram_total": round(mem.total / 1073741824, 1),
            "gpu_temp": gpu_temp, "gpu_load": round(gpu_load, 1),
            "vram_pct": round(vram_pct, 1),
            "vram_used": round(vram_used), "vram_total": round(vram_total),
        }
    except Exception as e:
        return {"cpu": 0, "ram_pct": 0, "ram_used": 0, "ram_total": 0, "gpu_temp": 0, "gpu_load": 0, "vram_pct": 0, "vram_used": 0, "vram_total": 0}


@app.get("/api/terminal/output")
async def term_output():
    running = _term_proc is not None and _term_proc.poll() is None
    return {"output": _term_output[-200:], "running": running}


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
        raise HTTPException(404, "Not found")
    import mimetypes
    ct = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=ct)


@app.delete("/api/files/{name}")
async def delete_file(name: str):
    p = os.path.join(UPLOAD_DIR, name)
    if os.path.exists(p):
        os.remove(p)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
