import os
import re
import math
import random
import string
import logging
import asyncio
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import StreamingResponse, HTMLResponse
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from motor.motor_asyncio import AsyncIOMotorClient

# --- CRITICAL FIX: Setup Event Loop First ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
# ------------------------------------------

logging.basicConfig(level=logging.INFO)

# Configs
API_ID = 32541562
API_HASH = "e37e4432298d5a5eb4a6e32c18804283"
BOT_TOKEN = "7886130082:AAE1IROKiE8rvDvX2aDK-En-2p_rnzkcX_Q"
MONGO_URI = "mongodb+srv://aaryansah954:QgDQRgyD7VUa7Eho@cluster0.wjo9zfm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
PORT = int(os.environ.get("PORT", 8080))
URL = os.environ.get("RENDER_EXTERNAL_URL", "https://as-file2link-bot.onrender.com").rstrip('/')

app = FastAPI()
db = AsyncIOMotorClient(MONGO_URI)["advance_stream_bot"]
files_db = db["files"]

# Pyrogram Client (in_memory to prevent SQLite locking on Render)
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- WEB SERVER ROUTES ---
@app.get("/")
async def root():
    return HTMLResponse("<h2 style='text-align:center;margin-top:20%;font-family:sans-serif;'>⚡ Stream Server is Live!</h2>")

@app.get("/watch/{file_code}")
async def watch_and_download(file_code: str, range: str = Header(None)):
    data = await files_db.find_one({"file_code": file_code})
    if not data: raise HTTPException(status_code=404, detail="File Not Found")

    msg = await bot.get_messages(data["chat_id"], data["msg_id"])
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

    return StreamingResponse(
        bot.stream_media(msg, offset=start, limit=length),
        status_code=206 if range else 200,
        headers=headers
    )

# --- TELEGRAM BOT ROUTES ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    print("✅ START COMMAND RECEIVED!") 
    await message.reply_text(
        f"👋 **Hey {message.from_user.first_name}! Bot Zinda Hai!**\n\n"
        "Forward me any **Video, Audio, or File** to get an **Instant Direct Download & High-Speed Stream Link**! 🚀"
    )

@bot.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def process_media(client: Client, message: Message):
    media = message.document or message.video or message.audio
    if not media: return

    status_msg = await message.reply_text("⚡ *Processing...*", quote=True)
    
    file_code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    file_name = getattr(media, "file_name", "Media_File.mp4")
    
    size_mb = round(media.file_size / (1024 * 1024), 2)
    file_size = f"{size_mb} MB"

    await files_db.insert_one({
        "file_code": file_code,
        "chat_id": message.chat.id,
        "msg_id": message.id
    })

    stream_url = f"{URL}/watch/{file_code}"
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Direct Download", url=stream_url), InlineKeyboardButton("📺 Watch Online", url=stream_url)]
    ])

    await status_msg.edit_text(
        text=f"📂 **Name:** `{file_name}`\n📦 **Size:** `{file_size}`\n\n🔗 **Link:** `{stream_url}`",
        reply_markup=buttons,
        disable_web_page_preview=True
    )

# --- EXECUTION ENGINE ---
async def main():
    # 1. FastAPI ko background loop me daalo taaki ye Telegram ko block na kare
    config = uvicorn.Config(app=app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    loop.create_task(server.serve())

    # 2. Pyrogram ko main loop me start karo
    await bot.start()
    print("✅ Bot Started and Listening for Messages!")
    
    # 3. Code ko zinda rakhne ke liye idle() use karo
    await idle()
    await bot.stop()

if __name__ == "__main__":
    loop.run_until_complete(main())
