"""
plugins/shortener.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Link Shortener — Paisa kamao ads se!

Admin Commands:
  /setshortener <API_KEY> <website.com>  — shortener set karo
  /removeshortener                       — shortener hata do
  /toggleshortener                       — on/off karo
  /shortener                             — current status dekho
  /setverifytime <n> <unit>              — verify time set karo (e.g. 12 hour)

Flow (Free users):
  1. User deep link kholne ki koshish karta hai
  2. Token banta hai → bot link → shortener se pass
  3. User ad complete kare → vfy_<token> pe aaye
  4. Temp premium milta hai (setverifytime duration)
  5. File/link mil jaata hai — koi waiting nahi

Premium users: shortener skip hota hai, direct link milta hai
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
import secrets

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot import Bot
from config import ADMINS
from database.database import (
    get_shortener_settings, set_bot_config, get_bot_config,
    has_premium_access,
)

log = logging.getLogger(__name__)


# ── Core shorten function ─────────────────────────────────────────

async def shorten_link(long_url: str) -> str:
    """URL ko short karo. Agar shortener off/error toh original return karo."""
    s = await get_shortener_settings()
    if not s["enabled"] or not s["api"] or not s["website"]:
        return long_url
    try:
        from shortzy import Shortzy
        sz = Shortzy(api_key=s["api"], base_site=s["website"])
        try:
            return await sz.convert(long_url)
        except Exception:
            return await sz.get_quick_link(long_url)
    except ImportError:
        log.warning("shortzy not installed → pip install shortzy")
        return long_url
    except Exception as e:
        log.error(f"Shortener error: {e}")
        return long_url


async def maybe_shorten(user_id: int, long_url: str) -> str:
    """
    Premium users ke liye: original link.
    Free users ke liye: shortened link (agar shortener ON hai).
    """
    s = await get_shortener_settings()
    if not s["enabled"]:
        return long_url
    if await has_premium_access(user_id):
        return long_url
    return await shorten_link(long_url)


# ── Verify time helper ────────────────────────────────────────────

async def _get_verify_seconds() -> int:
    cfg = await get_bot_config()
    return cfg.get("verify_premium_seconds", 86400)  # default 24h

def _parse_time(parts) -> int:
    """['12', 'hour'] → seconds"""
    try:
        val  = int(parts[0])
        unit = parts[1].lower()
        mult = {"s": 1, "sec": 1, "second": 1, "seconds": 1,
                "m": 60, "min": 60, "minute": 60, "minutes": 60,
                "h": 3600, "hour": 3600, "hours": 3600,
                "d": 86400, "day": 86400, "days": 86400}.get(unit, 0)
        return val * mult
    except Exception:
        return 0


# ── Admin Commands ────────────────────────────────────────────────

@Bot.on_message(filters.command("setshortener") & filters.private & filters.user(ADMINS))
async def cmd_set_shortener(client: Bot, msg: Message):
    """
    /setshortener API_KEY website.com
    Example: /setshortener a7ac9b3012c6 omegalinks.in
    """
    parts = msg.command
    if len(parts) < 3:
        return await msg.reply(
            "<b>📌 Usage:</b>\n"
            "<code>/setshortener API_KEY website.com</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/setshortener a7ac9b3012c6 omegalinks.in</code>\n\n"
            "<b>Supported sites:</b> omegalinks.in, urlshortx.com, shorte.st, etc.\n"
            "<i>(shortzy library se koi bhi site kaam karti hai)</i>"
        )

    api_key = parts[1]
    website = parts[2].strip().lower().replace("https://", "").replace("http://", "").rstrip("/")

    await set_bot_config("shortener_api", api_key)
    await set_bot_config("shortener_website", website)
    await set_bot_config("shortener_enabled", True)

    await msg.reply(
        f"✅ <b>Link Shortener Set!</b>\n\n"
        f"🔑 API Key: <code>{api_key[:8]}...</code>\n"
        f"🌐 Website: <code>{website}</code>\n"
        f"📊 Status: <b>ON ✅</b>\n\n"
        f"<i>Ab free users ko file link milne se pehle ad complete karna padega.</i>\n"
        f"<i>Premium users ko shortener bypass hoga.</i>"
    )


@Bot.on_message(filters.command("removeshortener") & filters.private & filters.user(ADMINS))
async def cmd_remove_shortener(client: Bot, msg: Message):
    await set_bot_config("shortener_api", "")
    await set_bot_config("shortener_website", "")
    await set_bot_config("shortener_enabled", False)
    await msg.reply("🗑 <b>Shortener remove ho gaya!</b>\nAb sabko direct links milenge.")


@Bot.on_message(filters.command("toggleshortener") & filters.private & filters.user(ADMINS))
async def cmd_toggle_shortener(client: Bot, msg: Message):
    s = await get_shortener_settings()
    if not s["api"] and not s["enabled"]:
        return await msg.reply("⚠️ Pehle <code>/setshortener</code> se API set karo!")
    new = not s["enabled"]
    await set_bot_config("shortener_enabled", new)
    status = "✅ ON" if new else "❌ OFF"
    await msg.reply(f"🔗 <b>Shortener:</b> <b>{status}</b>")


@Bot.on_message(filters.command("shortener") & filters.private & filters.user(ADMINS))
async def cmd_shortener_status(client: Bot, msg: Message):
    s = await get_shortener_settings()
    cfg = await get_bot_config()
    verify_sec = cfg.get("verify_premium_seconds", 86400)
    verify_hr  = verify_sec // 3600
    verify_min = (verify_sec % 3600) // 60

    status = "✅ ON" if s["enabled"] else "❌ OFF"
    api    = (s["api"][:8] + "...") if s["api"] else "❌ Not set"
    site   = s["website"] or "❌ Not set"
    dur    = f"{verify_hr}h" if verify_min == 0 else f"{verify_hr}h {verify_min}m"

    await msg.reply(
        f"<b>🔗 Link Shortener Status</b>\n\n"
        f"📊 Status: <b>{status}</b>\n"
        f"🔑 API Key: <code>{api}</code>\n"
        f"🌐 Website: <code>{site}</code>\n"
        f"⏰ Verify Time: <b>{dur}</b>\n\n"
        f"<b>Commands:</b>\n"
        f"<code>/setshortener API website</code>\n"
        f"<code>/toggleshortener</code>\n"
        f"<code>/removeshortener</code>\n"
        f"<code>/setverifytime 12 hour</code>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔴 Turn OFF" if s["enabled"] else "🟢 Turn ON",
                callback_data="shn_toggle"
            )
        ]])
    )


@Bot.on_message(filters.command("setverifytime") & filters.private & filters.user(ADMINS))
async def cmd_set_verify_time(client: Bot, msg: Message):
    """
    /setverifytime 12 hour
    /setverifytime 24 hour
    /setverifytime 1 day
    """
    parts = msg.command
    if len(parts) < 3:
        cfg = await get_bot_config()
        cur = cfg.get("verify_premium_seconds", 86400)
        h = cur // 3600
        m = (cur % 3600) // 60
        return await msg.reply(
            f"<b>⏰ Verify Time</b>\n\n"
            f"Current: <b>{h}h {m}m</b>\n\n"
            f"<b>Usage:</b>\n"
            f"<code>/setverifytime 6 hour</code>\n"
            f"<code>/setverifytime 12 hour</code>\n"
            f"<code>/setverifytime 24 hour</code>\n"
            f"<code>/setverifytime 1 day</code>\n\n"
            f"<i>Itni der tak user ko shortener dobara complete nahi karna padega.</i>"
        )

    seconds = _parse_time(parts[1:3])
    if seconds <= 0:
        return await msg.reply("❌ Invalid time! Example: <code>/setverifytime 12 hour</code>")

    await set_bot_config("verify_premium_seconds", seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    await msg.reply(f"✅ Verify time set: <b>{h}h {m}m</b>")


# ── Callback ──────────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex("^shn_toggle$"))
async def cb_toggle(client, query):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Admins only!", show_alert=True)
    s = await get_shortener_settings()
    if not s["api"] and not s["enabled"]:
        return await query.answer("⚠️ Pehle /setshortener se API set karo!", show_alert=True)
    new = not s["enabled"]
    await set_bot_config("shortener_enabled", new)
    await query.answer(f"{'✅ Shortener ON' if new else '❌ Shortener OFF'}", show_alert=True)
    try:
        await query.message.delete()
    except Exception:
        pass
