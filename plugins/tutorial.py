"""
plugins/tutorial.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tutorial video system

Admin Commands:
  /set_tutorial_fsub         — FSub join tutorial video set karo
  /set_tutorial_shortener    — Shortener tutorial video set karo
  /fsub_tutorial on/off      — FSub tutorial enable/disable
  /shortener_tutorial on/off — Shortener tutorial enable/disable

Flow (FSub):
  User FSub join nahi karta → 30s wait → video bhejo → 10min baad auto-delete

Flow (Shortener):
  User shortener complete nahi karta → 30s wait → video bhejo → 10min baad auto-delete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging

from pyrogram import filters
from pyrogram.types import Message

from bot import Bot
from config import ADMINS
from database.database import (
    set_tutorial, get_tutorial, toggle_tutorial,
    get_tutorial_status, get_verify_token,
)

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# /set_tutorial_fsub
# ═══════════════════════════════════════════

@Bot.on_message(filters.command("set_tutorial_fsub") & filters.private & filters.user(ADMINS))
async def cmd_set_tutorial_fsub(client: Bot, message: Message):
    """FSub tutorial video set karo."""
    prompt = await message.reply(
        "<b>📹 FSub Tutorial Set</b>\n\n"
        "<blockquote>Ab woh video bhejo jo FSub join nahi karne wale users ko dikhana hai.\n\n"
        "⏳ 5 minute ka wait hai.</blockquote>"
    )

    try:
        response = await client.listen(chat_id=message.chat.id, timeout=300)
    except asyncio.TimeoutError:
        await prompt.edit("<b>⏰ Timeout! Dobara /set_tutorial_fsub try karo.</b>")
        return

    file_id = _extract_file_id(response)

    if not file_id:
        await prompt.edit(
            "<b>❌ Sirf video ya document bhejo!</b>\n"
            "Dobara /set_tutorial_fsub try karo."
        )
        return

    try:
        await response.delete()
    except Exception:
        pass

    success = await set_tutorial("fsub", file_id)
    if success:
        await prompt.edit(
            "<b>✅ FSub Tutorial Video Set Ho Gaya!</b>\n\n"
            "<blockquote>"
            "Jo user 30 second mein FSub join nahi karega,\n"
            "usse yeh video jaegi aur 10 min baad delete ho jaegi.\n\n"
            "📌 Tutorial abhi <b>ON</b> hai.\n"
            "Band karne ke liye: <code>/fsub_tutorial off</code>"
            "</blockquote>"
        )
    else:
        await prompt.edit("<b>❌ Save karne mein error. Dobara try karo.</b>")


# ═══════════════════════════════════════════
# /set_tutorial_shortener
# ═══════════════════════════════════════════

@Bot.on_message(filters.command("set_tutorial_shortener") & filters.private & filters.user(ADMINS))
async def cmd_set_tutorial_shortener(client: Bot, message: Message):
    """Shortener tutorial video set karo."""
    prompt = await message.reply(
        "<b>📹 Shortener Tutorial Set</b>\n\n"
        "<blockquote>Ab woh video bhejo jo shortener complete nahi karne wale users ko dikhana hai.\n\n"
        "⏳ 5 minute ka wait hai.</blockquote>"
    )

    try:
        response = await client.listen(chat_id=message.chat.id, timeout=300)
    except asyncio.TimeoutError:
        await prompt.edit("<b>⏰ Timeout! Dobara /set_tutorial_shortener try karo.</b>")
        return

    file_id = _extract_file_id(response)

    if not file_id:
        await prompt.edit(
            "<b>❌ Sirf video ya document bhejo!</b>\n"
            "Dobara /set_tutorial_shortener try karo."
        )
        return

    try:
        await response.delete()
    except Exception:
        pass

    success = await set_tutorial("shortener", file_id)
    if success:
        await prompt.edit(
            "<b>✅ Shortener Tutorial Video Set Ho Gaya!</b>\n\n"
            "<blockquote>"
            "Jo user shortener complete nahi karega,\n"
            "usse yeh video jaegi aur 10 min baad delete ho jaegi.\n\n"
            "📌 Tutorial abhi <b>ON</b> hai.\n"
            "Band karne ke liye: <code>/shortener_tutorial off</code>"
            "</blockquote>"
        )
    else:
        await prompt.edit("<b>❌ Save karne mein error. Dobara try karo.</b>")


# ═══════════════════════════════════════════
# /fsub_tutorial on/off
# ═══════════════════════════════════════════

@Bot.on_message(filters.command("fsub_tutorial") & filters.private & filters.user(ADMINS))
async def cmd_toggle_fsub_tutorial(client: Bot, message: Message):
    args = message.command
    if len(args) < 2 or args[1].lower() not in ("on", "off"):
        status = await get_tutorial_status("fsub")
        current  = "✅ ON" if status["enabled"] else "❌ OFF"
        set_info = "✅ Set hai" if status["exists"] else "❌ Set nahi hai"
        return await message.reply(
            f"<b>📹 FSub Tutorial Status</b>\n\n"
            f"<blockquote>"
            f"Video: {set_info}\n"
            f"Status: {current}\n\n"
            f"Usage:\n"
            f"<code>/fsub_tutorial on</code>\n"
            f"<code>/fsub_tutorial off</code>"
            f"</blockquote>"
        )

    enabled = args[1].lower() == "on"
    status  = await get_tutorial_status("fsub")

    if enabled and not status["exists"]:
        return await message.reply(
            "<b>❌ Pehle tutorial video set karo!</b>\n"
            "Command: <code>/set_tutorial_fsub</code>"
        )

    ok = await toggle_tutorial("fsub", enabled)
    if ok:
        emoji = "✅" if enabled else "❌"
        await message.reply(f"<b>{emoji} FSub Tutorial {'ON' if enabled else 'OFF'} Ho Gaya!</b>")
    else:
        await message.reply("<b>❌ Update nahi hua. Pehle /set_tutorial_fsub se video set karo.</b>")


# ═══════════════════════════════════════════
# /shortener_tutorial on/off
# ═══════════════════════════════════════════

@Bot.on_message(filters.command("shortener_tutorial") & filters.private & filters.user(ADMINS))
async def cmd_toggle_shortener_tutorial(client: Bot, message: Message):
    args = message.command
    if len(args) < 2 or args[1].lower() not in ("on", "off"):
        status = await get_tutorial_status("shortener")
        current  = "✅ ON" if status["enabled"] else "❌ OFF"
        set_info = "✅ Set hai" if status["exists"] else "❌ Set nahi hai"
        return await message.reply(
            f"<b>📹 Shortener Tutorial Status</b>\n\n"
            f"<blockquote>"
            f"Video: {set_info}\n"
            f"Status: {current}\n\n"
            f"Usage:\n"
            f"<code>/shortener_tutorial on</code>\n"
            f"<code>/shortener_tutorial off</code>"
            f"</blockquote>"
        )

    enabled = args[1].lower() == "on"
    status  = await get_tutorial_status("shortener")

    if enabled and not status["exists"]:
        return await message.reply(
            "<b>❌ Pehle tutorial video set karo!</b>\n"
            "Command: <code>/set_tutorial_shortener</code>"
        )

    ok = await toggle_tutorial("shortener", enabled)
    if ok:
        emoji = "✅" if enabled else "❌"
        await message.reply(f"<b>{emoji} Shortener Tutorial {'ON' if enabled else 'OFF'} Ho Gaya!</b>")
    else:
        await message.reply("<b>❌ Update nahi hua. Pehle /set_tutorial_shortener se video set karo.</b>")


# ═══════════════════════════════════════════
# CORE SENDER FUNCTIONS
# start.py se asyncio.create_task ke zariye call hote hain
# ═══════════════════════════════════════════

async def send_fsub_tutorial_if_not_joined(client, user_id: int, check_func):
    """
    30s wait → agar user FSub join nahi kiya → tutorial video bhejo.
    check_func: async (user_id) -> bool  (True = joined)
    """
    tutorial = await get_tutorial("fsub")
    if not tutorial:
        return

    await asyncio.sleep(30)

    try:
        joined = await check_func(user_id)
    except Exception as e:
        log.error(f"fsub tutorial check_func error: {e}")
        return

    if joined:
        return

    try:
        sent = await client.send_video(
            chat_id=user_id,
            video=tutorial["file_id"],
            caption=(
                "<b>📹 FSub Join Kaise Karein?</b>\n\n"
                "<blockquote>"
                "Lagta hai aapko channel join karne mein problem aa rahi hai.\n"
                "Upar diya gaya tutorial dekho aur step follow karo! 👆\n\n"
                "⏰ Yeh message 10 minute mein delete ho jaega."
                "</blockquote>"
            )
        )
        asyncio.create_task(_delete_after(sent, 600))
        log.info(f"FSub tutorial sent to {user_id}")
    except Exception as e:
        log.error(f"send_fsub_tutorial error for {user_id}: {e}")


async def send_shortener_tutorial_if_not_verified(client, user_id: int, token: str):
    """
    30s wait → agar token use nahi hua → tutorial video bhejo.
    """
    tutorial = await get_tutorial("shortener")
    if not tutorial:
        return

    await asyncio.sleep(30)

    try:
        doc = await get_verify_token(token)
        if doc and doc.get("used"):
            return
    except Exception as e:
        log.error(f"shortener tutorial token check error: {e}")
        return

    try:
        sent = await client.send_video(
            chat_id=user_id,
            video=tutorial["file_id"],
            caption=(
                "<b>📹 Link Shortener Kaise Complete Karein?</b>\n\n"
                "<blockquote>"
                "Lagta hai aapko link shortener complete karne mein problem aa rahi hai.\n"
                "Upar diya gaya tutorial dekho aur step follow karo! 👆\n\n"
                "⏰ Yeh message 10 minute mein delete ho jaega."
                "</blockquote>"
            )
        )
        asyncio.create_task(_delete_after(sent, 600))
        log.info(f"Shortener tutorial sent to {user_id}")
    except Exception as e:
        log.error(f"send_shortener_tutorial error for {user_id}: {e}")


# ── Helper ────────────────────────────────────────────────────────

def _extract_file_id(message) -> str | None:
    """Message se video/document/animation file_id nikalo."""
    if message.video:
        return message.video.file_id
    if message.document:
        return message.document.file_id
    if message.animation:
        return message.animation.file_id
    return None


async def _delete_after(msg, delay: int):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass
