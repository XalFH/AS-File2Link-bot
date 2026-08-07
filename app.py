import asyncio
import sys

# Crucial Event Loop Fix for Render / Python 3.11+
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import re
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import StreamingResponse, HTMLResponse

import config
from database import files_db
from main import bot

# Lifespan hook properly starts Bot alongside FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting Pyrogram Bot...")
    await bot.start()
    print("✅ Pyrogram Bot Started Successfully & Listening!")
    yield
    print("🛑 Stopping Telegram Bot...")
    await bot.stop()

app = FastAPI(title="Stream Engine", lifespan=lifespan)

@app.get("/")
async def root():
    return HTMLResponse("<h2 style='text-align:center;margin-top:20%;font-family:sans-serif;'>⚡ Stream Server is Live!</h2>")

@app.get("/watch/{file_code}")
async def watch_and_download(file_code: str, range: str = Header(None)):
    data = await files_db.find_one({"file_code": file_code})
    if not data: raise HTTPException(status_code=404, detail="File Not Found")

    try:
        msg = await bot.get_messages(data["chat_id"], data["msg_id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Cannot fetch from Telegram")

    media = msg.document or msg.video or msg.audio
    file_size = media.file_size
    mime_type = getattr(media, "mime_type", "video/mp4")

    start, end = 0, file_size - 1

    if range:
        match = re.search(r"bytes=(\d+)-(\d*)", range)
        if match:
            start = int(match.group(1))
            if match.group(2): end = int(match.group(2))

    length = end - start + 1
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Type": mime_type,
        "Content-Disposition": f'inline; filename="{getattr(media, "file_name", "file.mp4")}"',
    }

    status_code = 206 if range else 200
    return StreamingResponse(
        bot.stream_media(msg, offset=start, limit=length),
        status_code=status_code,
        headers=headers
    )

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=config.PORT)
