import os
import re
import math
import random
import string
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Event loop fix for Pyrogram imports
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import FloodWait

from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import StreamingResponse, HTMLResponse
import uvicorn

# Logging Configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Credentials & Setup
API_ID = 32541562
API_HASH = "e37e4432298d5a5eb4a6e32c18804283"
BOT_TOKEN = "8932447404:AAFh62pQmAJ9n5H9mNUSNHl2fgjWxPjI_Hs"
MONGO_URI = "mongodb+srv://aryankumarsha20:CjdV5plwbpvwTTCU@cluster0.3zw5xk8.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
ADMIN_ID = 7006602588

PORT = int(os.environ.get("PORT", 8080))
URL = os.environ.get("RENDER_EXTERNAL_URL", "https://as-file2link-bot.onrender.com").rstrip('/')

# Database Setup
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["advance_stream_bot"]
files_db = db["files"]
users_db = db["users"]

# Pyrogram Client Setup
bot = Client(
    "AdvanceStreamBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Manage Lifespan properly so Pyrogram & FastAPI run smoothly together
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Starting Pyrogram Bot...")
    await bot.start()
    logging.info("Pyrogram Bot Started Successfully & Listening!")
    yield
    logging.info("Stopping Pyrogram Bot...")
    await bot.stop()

# FastAPI App
app = FastAPI(title="Stream Engine", lifespan=lifespan)

# Helper Functions
def humanbytes(size: int) -> str:
    if not size:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return f"{s} {units[i]}"

async def yield_file_chunks(media_msg: Message, start: int, length: int) -> AsyncGenerator[bytes, None]:
    async for chunk in bot.stream_media(media_msg, offset=start, limit=length):
        yield chunk

# Web Routes
@app.get("/")
async def root():
    return HTMLResponse("<h2 style='text-align:center;margin-top:20%;font-family:sans-serif;'>⚡ Stream Server is Live & Running!</h2>")

@app.get("/watch/{file_code}")
async def watch_and_download(file_code: str, request: Request, range: str = Header(None)):
    data = await files_db.find_one({"file_code": file_code})
    if not data:
        raise HTTPException(status_code=404, detail="File Not Found")

    msg_id = data["msg_id"]
    chat_id = data["chat_id"]

    try:
        media_msg = await bot.get_messages(chat_id, msg_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to retrieve media from Telegram")

    media = media_msg.document or media_msg.video or media_msg.audio
    file_size = media.file_size
    mime_type = getattr(media, "mime_type", "video/mp4")
    file_name = getattr(media, "file_name", "file.mp4")

    start = 0
    end = file_size - 1

    if range:
        match = re.search(r"bytes=(\d+)-(\d*)", range)
        if match:
            start = int(match.group(1))
            if match.group(2):
                end = int(match.group(2))

    length = end - start + 1
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Type": mime_type,
        "Content-Disposition": f'inline; filename="{file_name}"',
    }

    status_code = 206 if range else 200
    return StreamingResponse(
        yield_file_chunks(media_msg, start, length),
        status_code=status_code,
        headers=headers
    )

# Telegram Bot Events
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    await users_db.update_one({"_id": user_id}, {"$set": {"name": message.from_user.first_name}}, upsert=True)

    await message.reply_text(
        f"👋 **Hey {message.from_user.first_name}!**\n\n"
        "Send or forward me any **Video, Audio, or File**, and I will generate an **Instant Direct Download & High-Speed Online Stream Link** for you!\n\n"
        "⚡ *Supported features:* Fast Forward (Seeking), Resume Downloads, High Speed.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Developer", url="https://t.me/")]
        ])
    )

@bot.on_message(filters.command("stats") & filters.private & filters.user(ADMIN_ID))
async def stats_cmd(client: Client, message: Message):
    total_users = await users_db.count_documents({})
    total_files = await files_db.count_documents({})
    await message.reply_text(f"📊 **Bot Analytics:**\n\n👥 Total Users: `{total_users}`\n📁 Total Files Saved: `{total_files}`")

@bot.on_message(filters.command("broadcast") & filters.private & filters.user(ADMIN_ID))
async def broadcast_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to broadcast!")

    msg = await message.reply_text("🚀 Starting Broadcast...")
    users = users_db.find({})
    success, failed = 0, 0

    async for user in users:
        try:
            await message.reply_to_message.copy(chat_id=user["_id"])
            success += 1
            await asyncio.sleep(0.1)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await message.reply_to_message.copy(chat_id=user["_id"])
            success += 1
        except Exception:
            failed += 1

    await msg.edit_text(f"✅ **Broadcast Completed!**\n\n🎯 Success: `{success}`\n❌ Failed: `{failed}`")

@bot.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def process_media(client: Client, message: Message):
    media = message.document or message.video or message.audio
    if not media:
        return

    status_msg = await message.reply_text("⚡ *Generating High-Speed Links...*", quote=True)
    
    file_code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    file_name = getattr(media, "file_name", "Media_File.mp4")
    file_size = humanbytes(media.file_size)

    # Store file metadata in MongoDB
    await files_db.insert_one({
        "file_code": file_code,
        "chat_id": message.chat.id,
        "msg_id": message.id,
        "file_name": file_name,
        "file_size": media.file_size
    })

    stream_url = f"{URL}/watch/{file_code}"

    caption = (
        f"📂 **File Name:** `{file_name}`\n"
        f"📦 **File Size:** `{file_size}`\n\n"
        f"🚀 **Direct Stream / Download Link:**\n`{stream_url}`"
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Direct Download", url=stream_url),
            InlineKeyboardButton("📺 Watch Online", url=stream_url)
        ]
    ])

    await status_msg.edit_text(text=caption, reply_markup=buttons, disable_web_page_preview=True)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
