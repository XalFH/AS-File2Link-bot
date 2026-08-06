import os
import re
import math
import random
import string
import logging
import asyncio
from contextlib import asynccontextmanager
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import StreamingResponse, HTMLResponse
import uvicorn

# Configuration
API_ID = 32541562
API_HASH = "e37e4432298d5a5eb4a6e32c18804283"
BOT_TOKEN = "7886130082:AAE1IROKiE8rvDvX2aDK-En-2p_rnzkcX_Q"
MONGO_URI = "mongodb+srv://aryankumarsha20:CjdV5plwbpvwTTCU@cluster0.3zw5xk8.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
ADMIN_ID = 7006602588
PORT = int(os.environ.get("PORT", 8080))
URL = os.environ.get("RENDER_EXTERNAL_URL", "https://as-file2link-bot.onrender.com").rstrip('/')

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Databases & Clients
db = AsyncIOMotorClient(MONGO_URI)["advance_stream_bot"]
bot = Client("my_bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Lifespan: Bot aur Server ek saath start honge
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Telegram Bot...")
    await bot.start()
    logger.info("Bot Started Successfully!")
    yield
    logger.info("Stopping Bot...")
    await bot.stop()

app = FastAPI(lifespan=lifespan)

# Web Stream Route
@app.get("/watch/{file_code}")
async def stream(file_code: str, request: Request, range: str = Header(None)):
    data = await db.files.find_one({"file_code": file_code})
    if not data: raise HTTPException(status_code=404, detail="File not found")
    
    msg = await bot.get_messages(data["chat_id"], data["msg_id"])
    media = msg.document or msg.video or msg.audio
    
    start, end = 0, media.file_size - 1
    if range:
        match = re.search(r"bytes=(\d+)-(\d*)", range)
        if match:
            start = int(match.group(1))
            if match.group(2): end = int(match.group(2))
    
    return StreamingResponse(
        bot.stream_media(msg, offset=start, limit=end-start+1),
        status_code=206,
        headers={
            "Content-Range": f"bytes {start}-{end}/{media.file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Content-Type": getattr(media, "mime_type", "video/mp4")
        }
    )

# Telegram Handlers
@bot.on_message(filters.command("start"))
async def start(c, m):
    await m.reply("Bot is online! Forward me any file to get a link.")

@bot.on_message(filters.document | filters.video | filters.audio)
async def handle_file(c, m):
    code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    await db.files.insert_one({"file_code": code, "chat_id": m.chat.id, "msg_id": m.id})
    link = f"{URL}/watch/{code}"
    await m.reply(f"🚀 Link generated:\n{link}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Download", url=link)]]))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)
