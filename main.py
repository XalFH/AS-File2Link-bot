import asyncio

# --- CRITICAL EVENT LOOP FIX FOR PYTHON 3.14 ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
# -----------------------------------------------

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import config
from database import files_db, users_db
import utils

bot = Client(
    "AdvanceStreamBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    in_memory=True
)

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    print(f"✅ Received /start from User ID: {message.from_user.id}") # Render logs me dikhega
    
    # Database me save hone se pehle hi bot reply bhejega
    msg = await message.reply_text("⏳ Processing...")
    
    try:
        await users_db.update_one(
            {"_id": message.from_user.id}, 
            {"$set": {"name": message.from_user.first_name}}, 
            upsert=True
        )
        print("✅ MongoDB Update Successful!")
    except Exception as e:
        print(f"❌ MONGODB ERROR: {e}")
        await msg.edit_text(f"❌ Database Connection Error: `{e}`\n\nBhai, MongoDB Atlas me Network Access check karo (0.0.0.0/0).")
        return

    await msg.edit_text(
        f"👋 **Hey {message.from_user.first_name}!**\n\n"
        "Forward me any **Video, Audio, or File** to get an **Instant Direct Download & High-Speed Stream Link**! 🚀",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Developer", url="https://t.me/")]])
    )

@bot.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def process_media(client: Client, message: Message):
    media = message.document or message.video or message.audio
    if not media: return

    status_msg = await message.reply_text("⚡ *Processing and Saving...*", quote=True)
    
    file_code = utils.generate_code()
    file_name = getattr(media, "file_name", "Media_File.mp4")
    file_size = utils.humanbytes(media.file_size)

    try:
        await files_db.insert_one({
            "file_code": file_code,
            "chat_id": message.chat.id,
            "msg_id": message.id,
            "file_size": media.file_size
        })
    except Exception as e:
        await status_msg.edit_text(f"❌ DB Error: `{e}`")
        return

    stream_url = f"{config.URL}/watch/{file_code}"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Direct Download", url=stream_url),
         InlineKeyboardButton("📺 Watch Online", url=stream_url)]
    ])

    await status_msg.edit_text(
        text=f"📂 **Name:** `{file_name}`\n📦 **Size:** `{file_size}`\n\n🔗 **Link:** `{stream_url}`",
        reply_markup=buttons,
        disable_web_page_preview=True
    )
