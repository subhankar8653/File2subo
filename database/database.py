import datetime
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME

dbclient = AsyncIOMotorClient(MONGO_URI)
database = dbclient[DB_NAME]

user_col         = database["users"]
admin_col        = database["admins"]
banned_col       = database["banned"]
fsub_col         = database["fsub_channels"]
settings_col     = database["settings"]
fake_link_col    = database["fake_link"]
fsub_requests_col = database["fsub_pending_requests"]

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

async def get_fsub_channel_name(channel_id: int) -> str | None:
    doc = await fsub_col.find_one({"_id": channel_id})
    return (doc.get("custom_name") or None) if doc else None

async def set_fsub_channel_name(channel_id: int, custom_name: str) -> bool:
    try:
        result = await fsub_col.update_one(
            {"_id": channel_id},
            {"$set": {"custom_name": custom_name.strip()}},
            upsert=False
        )
        return result.matched_count > 0
    except Exception as e:
        logging.error(f"set_fsub_channel_name error: {e}")
        return False

async def clear_fsub_channel_name(channel_id: int):
    await fsub_col.update_one({"_id": channel_id}, {"$unset": {"custom_name": ""}})

# ── FSub Pending Requests ─────────────────────────────────────────

async def add_fsub_request(channel_id: int, user_id: int):
    doc_id = f"{channel_id}_{user_id}"
    if not await fsub_requests_col.find_one({"_id": doc_id}):
        await fsub_requests_col.insert_one({
            "_id": doc_id,
            "channel_id": channel_id,
            "user_id": user_id,
        })

async def has_fsub_request(channel_id: int, user_id: int) -> bool:
    doc_id = f"{channel_id}_{user_id}"
    return bool(await fsub_requests_col.find_one({"_id": doc_id}))

async def remove_fsub_request(channel_id: int, user_id: int):
    doc_id = f"{channel_id}_{user_id}"
    await fsub_requests_col.delete_one({"_id": doc_id})

# ── Request Mode ──────────────────────────────────────────────────

async def get_fsub_request_mode() -> bool:
    doc = await settings_col.find_one({"_id": "request_mode"})
    return bool(doc["value"]) if doc else False

async def set_fsub_request_mode(enabled: bool):
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

async def set_fake_link(url: str, button_text: str) -> bool:
    try:
        await fake_link_col.update_one(
            {"_id": "config"},
            {"$set": {"url": url, "button_text": button_text, "enabled": True}},
            upsert=True,
        )
        return True
    except Exception as e:
        logging.error(f"set_fake_link error: {e}")
        return False

async def get_fake_link() -> dict | None:
    try:
        doc = await fake_link_col.find_one({"_id": "config"})
        if doc and doc.get("enabled"):
            return {"url": doc["url"], "button_text": doc["button_text"]}
        return None
    except Exception as e:
        logging.error(f"get_fake_link error: {e}")
        return None

async def remove_fake_link() -> bool:
    try:
        result = await fake_link_col.delete_one({"_id": "config"})
        return result.deleted_count > 0
    except Exception as e:
        logging.error(f"remove_fake_link error: {e}")
        return False

# ── Bot Config (shortener, tutorial, etc.) ───────────────────────

bot_config_col = database["bot_config"]

async def get_bot_config() -> dict:
    doc = await bot_config_col.find_one({"_id": "main"})
    return doc or {}

async def set_bot_config(key: str, value) -> None:
    await bot_config_col.update_one(
        {"_id": "main"}, {"$set": {key: value}}, upsert=True
    )

# ── Shortener ─────────────────────────────────────────────────────

async def get_shortener_settings() -> dict:
    cfg = await get_bot_config()
    return {
        "enabled": cfg.get("shortener_enabled", False),
        "api":     cfg.get("shortener_api", ""),
        "website": cfg.get("shortener_website", ""),
    }

# ── Premium ───────────────────────────────────────────────────────

premium_col = database["premium_users"]

async def has_premium_access(user_id: int) -> bool:
    try:
        doc = await premium_col.find_one({"_id": user_id})
        if not doc:
            return False
        expiry = doc.get("expiry_time")
        if expiry and datetime.datetime.now() <= expiry:
            return True
        await premium_col.update_one({"_id": user_id}, {"$set": {"expiry_time": None}})
        return False
    except Exception as e:
        logging.error(f"has_premium_access error: {e}")
        return False

async def get_premium_expiry(user_id: int):
    try:
        doc = await premium_col.find_one({"_id": user_id})
        return doc.get("expiry_time") if doc else None
    except Exception as e:
        logging.error(f"get_premium_expiry error: {e}")
        return None

async def add_premium(user_id: int, seconds: int) -> bool:
    try:
        expiry = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        await premium_col.update_one(
            {"_id": user_id},
            {"$set": {"expiry_time": expiry}},
            upsert=True
        )
        return True
    except Exception as e:
        logging.error(f"add_premium error: {e}")
        return False

async def remove_premium(user_id: int) -> bool:
    try:
        result = await premium_col.update_one({"_id": user_id}, {"$set": {"expiry_time": None}})
        return result.matched_count > 0
    except Exception as e:
        logging.error(f"remove_premium error: {e}")
        return False

async def get_all_premium_users() -> list:
    try:
        cursor = premium_col.find({"expiry_time": {"$gt": datetime.datetime.now()}})
        return [doc async for doc in cursor]
    except Exception as e:
        logging.error(f"get_all_premium_users error: {e}")
        return []

# ── Verify Tokens (Shortener flow) ───────────────────────────────

verify_tokens_col = database["verify_tokens"]

async def create_verify_token(user_id: int, token: str) -> bool:
    try:
        await verify_tokens_col.update_one(
            {"token": token},
            {"$set": {
                "token":      token,
                "user_id":    user_id,
                "created_at": datetime.datetime.now(),
                "used":       False,
            }},
            upsert=True
        )
        return True
    except Exception as e:
        logging.error(f"create_verify_token error: {e}")
        return False

async def get_verify_token(token: str) -> dict:
    try:
        doc = await verify_tokens_col.find_one({"token": token})
        return dict(doc) if doc else {}
    except Exception as e:
        logging.error(f"get_verify_token error: {e}")
        return {}

async def mark_token_used(token: str) -> bool:
    try:
        await verify_tokens_col.update_one({"token": token}, {"$set": {"used": True}})
        return True
    except Exception as e:
        logging.error(f"mark_token_used error: {e}")
        return False

async def delete_old_tokens():
    try:
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=1)
        await verify_tokens_col.delete_many({"created_at": {"$lt": cutoff}})
    except Exception as e:
        logging.error(f"delete_old_tokens error: {e}")

# ── Tutorial ──────────────────────────────────────────────────────

tutorial_col = database["tutorial_config"]

async def set_tutorial(tutorial_type: str, file_id: str) -> bool:
    try:
        await tutorial_col.update_one(
            {"_id": tutorial_type},
            {"$set": {
                "_id":        tutorial_type,
                "file_id":    file_id,
                "enabled":    True,
                "updated_at": datetime.datetime.utcnow(),
            }},
            upsert=True
        )
        return True
    except Exception as e:
        logging.error(f"set_tutorial error: {e}")
        return False

async def get_tutorial(tutorial_type: str) -> dict | None:
    try:
        doc = await tutorial_col.find_one({"_id": tutorial_type})
        if doc and doc.get("enabled", False):
            return {"file_id": doc["file_id"]}
        return None
    except Exception as e:
        logging.error(f"get_tutorial error: {e}")
        return None

async def toggle_tutorial(tutorial_type: str, enabled: bool) -> bool:
    try:
        result = await tutorial_col.update_one(
            {"_id": tutorial_type},
            {"$set": {"enabled": enabled, "updated_at": datetime.datetime.utcnow()}}
        )
        return result.matched_count > 0
    except Exception as e:
        logging.error(f"toggle_tutorial error: {e}")
        return False

async def get_tutorial_status(tutorial_type: str) -> dict:
    try:
        doc = await tutorial_col.find_one({"_id": tutorial_type})
        if not doc:
            return {"exists": False, "enabled": False, "file_id": None}
        return {
            "exists":   True,
            "enabled":  doc.get("enabled", False),
            "file_id":  doc.get("file_id"),
        }
    except Exception as e:
        logging.error(f"get_tutorial_status error: {e}")
        return {"exists": False, "enabled": False, "file_id": None}

# ── File-to-Link Channel ──────────────────────────────────────────

ftl_col = database["ftl_config"]

async def get_ftl_channel() -> int | None:
    try:
        doc = await ftl_col.find_one({"_id": "channel"})
        return doc["channel_id"] if doc else None
    except Exception as e:
        logging.error(f"get_ftl_channel error: {e}")
        return None

async def set_ftl_channel(channel_id: int) -> bool:
    try:
        await ftl_col.update_one(
            {"_id": "channel"},
            {"$set": {"channel_id": channel_id}},
            upsert=True,
        )
        return True
    except Exception as e:
        logging.error(f"set_ftl_channel error: {e}")
        return False

async def remove_ftl_channel() -> bool:
    try:
        result = await ftl_col.delete_one({"_id": "channel"})
        return result.deleted_count > 0
    except Exception as e:
        logging.error(f"remove_ftl_channel error: {e}")
        return False

# ── Batch Sessions (channel batch mode) ──────────────────────────

ftl_batch_col = database["ftl_batch_sessions"]

async def ftl_batch_start(channel_id: int) -> bool:
    try:
        await ftl_batch_col.update_one(
            {"_id": channel_id},
            {"$set": {"_id": channel_id, "files": [], "started_at": datetime.datetime.utcnow()}},
            upsert=True,
        )
        return True
    except Exception as e:
        logging.error(f"ftl_batch_start error: {e}")
        return False

async def ftl_batch_add(channel_id: int, msg_id: int, file_name: str) -> bool:
    try:
        await ftl_batch_col.update_one(
            {"_id": channel_id},
            {"$push": {"files": {"msg_id": msg_id, "name": file_name}}},
        )
        return True
    except Exception as e:
        logging.error(f"ftl_batch_add error: {e}")
        return False

async def ftl_batch_get(channel_id: int) -> list:
    try:
        doc = await ftl_batch_col.find_one({"_id": channel_id})
        return doc["files"] if doc else []
    except Exception as e:
        logging.error(f"ftl_batch_get error: {e}")
        return []

async def ftl_batch_exists(channel_id: int) -> bool:
    try:
        return bool(await ftl_batch_col.find_one({"_id": channel_id}))
    except Exception:
        return False

async def ftl_batch_clear(channel_id: int) -> bool:
    try:
        await ftl_batch_col.delete_one({"_id": channel_id})
        return True
    except Exception as e:
        logging.error(f"ftl_batch_clear error: {e}")
        return False
