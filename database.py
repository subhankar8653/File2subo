from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME, LOGGER

log = LOGGER(__name__)
_client = None

def get_db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URI)
    return _client[DB_NAME]

# ── Users ────────────────────────────────────────────────────────
async def add_user(user_id: int):
    db = get_db()
    await db.users.update_one({"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True)

async def user_exists(user_id: int) -> bool:
    db = get_db()
    return await db.users.find_one({"_id": user_id}) is not None

async def get_all_users() -> list:
    db = get_db()
    return [doc["_id"] async for doc in db.users.find()]

async def total_users() -> int:
    return len(await get_all_users())

# ── Admins ───────────────────────────────────────────────────────
async def add_admin(user_id: int):
    db = get_db()
    await db.admins.update_one({"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True)

async def remove_admin(user_id: int):
    db = get_db()
    await db.admins.delete_one({"_id": user_id})

async def is_admin(user_id: int) -> bool:
    from config import OWNER_ID
    if user_id == OWNER_ID:
        return True
    db = get_db()
    return await db.admins.find_one({"_id": user_id}) is not None

async def get_all_admins() -> list:
    db = get_db()
    return [doc["_id"] async for doc in db.admins.find()]

# ── Banned Users ─────────────────────────────────────────────────
async def ban_user(user_id: int):
    db = get_db()
    await db.banned.update_one({"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True)

async def unban_user(user_id: int):
    db = get_db()
    await db.banned.delete_one({"_id": user_id})

async def is_banned(user_id: int) -> bool:
    db = get_db()
    return await db.banned.find_one({"_id": user_id}) is not None

# ── Force Sub Channels ───────────────────────────────────────────
async def add_fsub(channel_id: int):
    db = get_db()
    await db.fsub.update_one({"_id": channel_id}, {"$set": {"_id": channel_id}}, upsert=True)

async def remove_fsub(channel_id: int):
    db = get_db()
    await db.fsub.delete_one({"_id": channel_id})

async def get_fsub_channels() -> list:
    db = get_db()
    return [doc["_id"] async for doc in db.fsub.find()]

# ── Settings ─────────────────────────────────────────────────────
async def get_setting(key: str, default=None):
    db = get_db()
    doc = await db.settings.find_one({"_id": key})
    return doc["value"] if doc else default

async def set_setting(key: str, value):
    db = get_db()
    await db.settings.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)
