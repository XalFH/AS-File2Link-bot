from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import config
from database import files_db, users_db
import utils

# Pyrogram Client Setup (in_memory=True fixes Render session conflicts)
bot = Client(
    "AdvanceStreamBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    in_memory=True
)

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    await users_db.update_one(
        {"_id": message.from_user.id}, 
        {"$set": {"name": message.from_user.first_name}}, 
        upsert=True
    )
    await message.reply_text(
        f"👋 **Hey {message.from_user.first_name}!**\n\n"
        "Forward me any **Video, Audio, or File** to get an **Instant Direct Download & High-Speed Stream Link**! 🚀",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Developer", url="https://t.me/")]])
    )

@bot.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def process_media(client: Client, message: Message):
    media = message.document or message.video or message.audio
    if not media: return

    status_msg = await message.reply_text("⚡ *Processing...*", quote=True)
    
    file_code = utils.generate_code()
    file_name = getattr(media, "file_name", "Media_File.mp4")
    file_size = utils.humanbytes(media.file_size)

    # Save to MongoDB
    await files_db.insert_one({
        "file_code": file_code,
        "chat_id": message.chat.id,
        "msg_id": message.id,
        "file_size": media.file_size
    })

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
