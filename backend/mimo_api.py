import aiohttp
import time
from backend.config import MIMO_URL

_cache = {"sessions": None, "ts": 0}


async def list_sessions():
    now = time.time()
    if _cache["sessions"] and now - _cache["ts"] < 2:
        return _cache["sessions"]
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{MIMO_URL}/session") as r:
            data = await r.json()
    result = []
    for ses in data:
        result.append({
            "id": ses["id"],
            "title": ses.get("title", "Untitled"),
            "created": ses.get("time", {}).get("created", 0),
        })
    result.sort(key=lambda x: x["created"], reverse=True)
    _cache["sessions"] = result
    _cache["ts"] = now
    return result


async def get_messages(session_id: str):
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{MIMO_URL}/session/{session_id}/message") as r:
            data = await r.json()
    messages = []
    for msg in data:
        role = msg.get("info", {}).get("role", "")
        if role not in ("user", "assistant"):
            continue
        text_parts = []
        for part in msg.get("parts", []):
            if part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        if text_parts:
            messages.append({"role": role, "text": "\n".join(text_parts)})
    return messages


async def send_message(session_id: str, text: str):
    payload = {"parts": [{"type": "text", "text": text}]}
    async with aiohttp.ClientSession() as s:
        async with s.post(
            f"{MIMO_URL}/session/{session_id}/prompt_async",
            json=payload
        ) as r:
            return r.status


async def create_session():
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{MIMO_URL}/session") as r:
            if r.status == 200 or r.status == 201:
                data = await r.json()
                return data.get("id")
    return None
