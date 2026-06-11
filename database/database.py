from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME

dbclient = AsyncIOMotorClient(MONGO_URI)
database = dbclient[DB_NAME]

user_col    = database["users"]
admin_col   = database["admins"]
banned_col  = database["banned"]
fsub_col    = database["fsub_channels"]
settings_col = database["settings"]

# ── Users ─────────────────────────────────────────────────────────

async def present_user(user_id: int) -> bool:
    return bool(await user_col.find_one({"_id": user_id}))

async def add_user(user_id: int):
    if not await present_user(user_id):
        await user_col.insert_one({"_id": user_id})

async def del_user(user_id: int):
    await user_col.delete_one({"_id": user_id})

async def full_userbase() -> list:
    return [doc["_id"] async for doc in user_col.find()]

async def total_users() -> int:
    return await user_col.count_documents({})

# ── Admins ────────────────────────────────────────────────────────

async def is_admin(user_id: int) -> bool:
    from config import ADMINS
    if user_id in ADMINS:
        return True
    return bool(await admin_col.find_one({"_id": user_id}))

async def add_admin(user_id: int):
    if not await admin_col.find_one({"_id": user_id}):
        await admin_col.insert_one({"_id": user_id})

async def remove_admin(user_id: int):
    await admin_col.delete_one({"_id": user_id})

async def get_all_admins() -> list:
    return [doc["_id"] async for doc in admin_col.find()]

# ── Banned ────────────────────────────────────────────────────────

async def is_banned(user_id: int) -> bool:
    return bool(await banned_col.find_one({"_id": user_id}))

async def ban_user(user_id: int):
    if not await banned_col.find_one({"_id": user_id}):
        await banned_col.insert_one({"_id": user_id})

async def unban_user(user_id: int):
    await banned_col.delete_one({"_id": user_id})

# ── Force Sub ─────────────────────────────────────────────────────

async def add_fsub(channel_id: int):
    if not await fsub_col.find_one({"_id": channel_id}):
        await fsub_col.insert_one({"_id": channel_id})

async def remove_fsub(channel_id: int):
    await fsub_col.delete_one({"_id": channel_id})

async def get_fsub_channels() -> list:
    return [doc["_id"] async for doc in fsub_col.find()]

# ── Settings ──────────────────────────────────────────────────────

async def get_setting(key: str, default=None):
    doc = await settings_col.find_one({"_id": key})
    return doc["value"] if doc else default

async def set_setting(key: str, value):
    await settings_col.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)
