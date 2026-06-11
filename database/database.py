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

async def get_fsub_request_mode() -> bool:
    """Global request mode — agar True hai to FSub channels join-request link banayenge."""
    doc = await settings_col.find_one({"_id": "request_mode"})
    return bool(doc["value"]) if doc else False

async def set_fsub_request_mode(enabled: bool):
    """Global request mode on/off karo."""
    await settings_col.update_one(
        {"_id": "request_mode"},
        {"$set": {"value": enabled}},
        upsert=True,
    )

# ── Settings ──────────────────────────────────────────────────────

async def get_setting(key: str, default=None):
    doc = await settings_col.find_one({"_id": key})
    return doc["value"] if doc else default

async def set_setting(key: str, value):
    await settings_col.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)

# ── Fake Link ─────────────────────────────────────────────────────

fake_link_col = database["fake_link"]

async def set_fake_link(url: str, button_text: str) -> bool:
    """Fake link set karo — FSub message mein sabse pehle button dikhega."""
    try:
        await fake_link_col.update_one(
            {"_id": "config"},
            {"$set": {"url": url, "button_text": button_text, "enabled": True}},
            upsert=True,
        )
        return True
    except Exception as e:
        import logging; logging.error(f"set_fake_link error: {e}")
        return False

async def get_fake_link() -> dict | None:
    """Fake link config fetch karo. None return hoga agar set nahi ya disabled ho."""
    try:
        doc = await fake_link_col.find_one({"_id": "config"})
        if doc and doc.get("enabled"):
            return {"url": doc["url"], "button_text": doc["button_text"]}
        return None
    except Exception as e:
        import logging; logging.error(f"get_fake_link error: {e}")
        return None

async def remove_fake_link() -> bool:
    """Fake link hata do."""
    try:
        result = await fake_link_col.delete_one({"_id": "config"})
        return result.deleted_count > 0
    except Exception as e:
        import logging; logging.error(f"remove_fake_link error: {e}")
        return False
