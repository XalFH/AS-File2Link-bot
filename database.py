from motor.motor_asyncio import AsyncIOMotorClient
import config

# Initialize MongoDB
db_client = AsyncIOMotorClient(config.MONGO_URI)
db = db_client["advance_stream_bot"]

files_db = db["files"]
users_db = db["users"]
