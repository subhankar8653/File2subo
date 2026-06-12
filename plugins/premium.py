"""
plugins/premium.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Premium Membership System

Admin Commands:
  /addpremium <user_id> <amount> <unit>   — Premium do (e.g. /addpremium 123456789 30 day)
  /removepremium <user_id>                — Premium hata do
  /premiumusers                           — Sabhi active premium users dekho
  /premiuminfo <user_id>                  — Kisi specific user ka premium status dekho

User Commands:
  /myplan                                  — Apna premium status check karo
  /plan                                    — Premium benefits ke baare mein jaano

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PREMIUM PRIORITY (fast-path, no waiting):
  • FSub bypass        → helper_func.is_subscribed
  • Link Shortener skip → plugins/start.py + plugins/shortener.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import datetime
import logging

from pyrogram import filters
from pyrogram.types import Message

from bot import Bot
from config import ADMINS, LOG_CHANNEL
from helper_func import parse_duration
from database.database import (
    has_premium_access, get_premium_expiry,
    add_premium, remove_premium, get_all_premium_users,
)

log = logging.getLogger(__name__)


# ── Time-left formatter ────────────────────────────────────────────

def _time_left_str(expiry: datetime.datetime) -> str:
    now = datetime.datetime.now()
    delta = expiry - now
    if delta.total_seconds() <= 0:
        return "Expired"
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m"


def _expiry_str(expiry: datetime.datetime) -> str:
    return expiry.strftime("%d-%m-%Y %I:%M:%S %p")


def _duration_str(seconds: int) -> str:
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


# ── /addpremium <user_id> <amount> <unit> ───────────────────────────

@Bot.on_message(filters.command("addpremium") & filters.private & filters.user(ADMINS))
async def cmd_add_premium(client: Bot, message: Message):
    if len(message.command) != 4:
        return await message.reply(
            "<b>📌 Usage:</b>\n"
            "<code>/addpremium user_id amount unit</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/addpremium 123456789 30 day</code>\n"
            "<code>/addpremium 123456789 12 hour</code>\n"
            "<code>/addpremium 123456789 1 month</code>\n"
            "<code>/addpremium 123456789 1 year</code>\n\n"
            "<b>Valid units:</b> min, hour, day, month, year"
        )

    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid user_id! Numeric ID do.")

    amount = message.command[2]
    unit = message.command[3]
    seconds = parse_duration(amount, unit)

    if seconds <= 0:
        return await message.reply(
            "❌ Invalid time format!\n\n"
            "Use: <code>/addpremium user_id amount unit</code>\n"
            "Example: <code>/addpremium 123456789 30 day</code>\n\n"
            "<b>Valid units:</b> min, hour, day, month, year"
        )

    try:
        user = await client.get_users(user_id)
        mention = user.mention
    except Exception:
        mention = f"<code>{user_id}</code>"

    ok = await add_premium(user_id, seconds)
    if not ok:
        return await message.reply("❌ Premium add karne mein error aaya. Try again.")

    expiry = await get_premium_expiry(user_id)
    expiry_text = _expiry_str(expiry) if expiry else "N/A"
    duration_text = _duration_str(seconds)

    await message.reply(
        f"✅ <b>Premium Added Successfully!</b>\n\n"
        f"👤 User: {mention}\n"
        f"🆔 User ID: <code>{user_id}</code>\n"
        f"⏰ Duration: <b>{duration_text}</b>\n"
        f"⌛ Expiry: <b>{expiry_text}</b>\n\n"
        f"🚀 <i>FSub aur Link Shortener — dono bypass, fast priority!</i>"
    )

    # ── Notify the user ──────────────────────────────────────────
    try:
        await client.send_message(
            chat_id=user_id,
            text=(
                f"🎉 <b>Congratulations!</b>\n\n"
                f"Aapko <b>Premium Membership</b> mil gayi hai!\n\n"
                f"⏰ Duration: <b>{duration_text}</b>\n"
                f"⌛ Expiry: <b>{expiry_text}</b>\n\n"
                f"<blockquote>"
                f"🚀 Ab aapke liye:\n"
                f"• No Force Subscribe ✅\n"
                f"• No Link Shortener / Ads ✅\n"
                f"• Direct & Fast File Access ⚡"
                f"</blockquote>\n\n"
                f"Check status anytime: /myplan"
            )
        )
    except Exception:
        pass

    # ── Log to LOG_CHANNEL ───────────────────────────────────────
    if LOG_CHANNEL:
        try:
            await client.send_message(
                chat_id=LOG_CHANNEL,
                text=(
                    f"#PremiumAdded\n\n"
                    f"👤 User: {mention}\n"
                    f"🆔 User ID: <code>{user_id}</code>\n"
                    f"⏰ Duration: <b>{duration_text}</b>\n"
                    f"⌛ Expiry: <b>{expiry_text}</b>\n"
                    f"👮 By: {message.from_user.mention}"
                )
            )
        except Exception:
            pass


# ── /removepremium <user_id> ────────────────────────────────────────

@Bot.on_message(filters.command("removepremium") & filters.private & filters.user(ADMINS))
async def cmd_remove_premium(client: Bot, message: Message):
    if len(message.command) != 2:
        return await message.reply("<b>📌 Usage:</b> <code>/removepremium user_id</code>")

    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid user_id! Numeric ID do.")

    if not await has_premium_access(user_id):
        return await message.reply("⚠️ Yeh user premium nahi hai (ya already expired).")

    ok = await remove_premium(user_id)
    if not ok:
        return await message.reply("❌ Premium remove karne mein error aaya.")

    try:
        user = await client.get_users(user_id)
        mention = user.mention
    except Exception:
        mention = f"<code>{user_id}</code>"

    await message.reply(
        f"✅ <b>Premium Removed!</b>\n\n"
        f"👤 User: {mention}\n"
        f"🆔 User ID: <code>{user_id}</code>"
    )

    try:
        await client.send_message(
            chat_id=user_id,
            text=(
                f"⚠️ <b>Your Premium Access Has Been Removed.</b>\n\n"
                f"Thank you for using our service! 😊\n\n"
                f"Check your status anytime: /myplan"
            )
        )
    except Exception:
        pass

    if LOG_CHANNEL:
        try:
            await client.send_message(
                chat_id=LOG_CHANNEL,
                text=(
                    f"#PremiumRemoved\n\n"
                    f"👤 User: {mention}\n"
                    f"🆔 User ID: <code>{user_id}</code>\n"
                    f"👮 By: {message.from_user.mention}"
                )
            )
        except Exception:
            pass


# ── /premiuminfo <user_id> ───────────────────────────────────────────

@Bot.on_message(filters.command("premiuminfo") & filters.private & filters.user(ADMINS))
async def cmd_premium_info(client: Bot, message: Message):
    if len(message.command) != 2:
        return await message.reply("<b>📌 Usage:</b> <code>/premiuminfo user_id</code>")

    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid user_id! Numeric ID do.")

    expiry = await get_premium_expiry(user_id)
    if not expiry or not await has_premium_access(user_id):
        return await message.reply(
            f"ℹ️ <code>{user_id}</code> ke paas koi active premium plan nahi hai."
        )

    try:
        user = await client.get_users(user_id)
        mention = user.mention
    except Exception:
        mention = f"<code>{user_id}</code>"

    await message.reply(
        f"⚜️ <b>Premium User Info</b>\n\n"
        f"👤 User: {mention}\n"
        f"🆔 User ID: <code>{user_id}</code>\n"
        f"⏳ Time Left: <b>{_time_left_str(expiry)}</b>\n"
        f"⌛ Expiry: <b>{_expiry_str(expiry)}</b>"
    )


# ── /premiumusers ─────────────────────────────────────────────────

@Bot.on_message(filters.command("premiumusers") & filters.private & filters.user(ADMINS))
async def cmd_premium_users(client: Bot, message: Message):
    wait_msg = await message.reply("⏳ <i>Fetching premium users...</i>")

    users = await get_all_premium_users()
    if not users:
        return await wait_msg.edit("ℹ️ Koi active premium user nahi hai.")

    text = f"⚜️ <b>Premium Users List ({len(users)})</b>\n\n"
    for i, doc in enumerate(users, start=1):
        uid = doc.get("_id")
        expiry = doc.get("expiry_time")
        try:
            user = await client.get_users(uid)
            mention = user.mention
        except Exception:
            mention = f"<code>{uid}</code>"
        text += (
            f"{i}. {mention}\n"
            f"    🆔 <code>{uid}</code>\n"
            f"    ⏳ Left: {_time_left_str(expiry)}\n"
            f"    ⌛ Expiry: {_expiry_str(expiry)}\n\n"
        )

    if len(text) <= 4096:
        await wait_msg.edit(text)
    else:
        with open("premium_users.txt", "w+", encoding="utf-8") as f:
            f.write(text)
        await wait_msg.delete()
        await message.reply_document("premium_users.txt", caption="⚜️ Premium Users List")


# ── /myplan ───────────────────────────────────────────────────────

@Bot.on_message(filters.command("myplan") & filters.private)
async def cmd_myplan(client: Bot, message: Message):
    user_id = message.from_user.id
    expiry = await get_premium_expiry(user_id)

    if expiry and await has_premium_access(user_id):
        await message.reply(
            f"⚜️ <b>Your Premium Plan</b>\n\n"
            f"👤 User: {message.from_user.mention}\n"
            f"🆔 User ID: <code>{user_id}</code>\n"
            f"⏳ Time Left: <b>{_time_left_str(expiry)}</b>\n"
            f"⌛ Expiry: <b>{_expiry_str(expiry)}</b>\n\n"
            f"<blockquote>🚀 No FSub. No Shortener. Fast & Direct! ✅</blockquote>"
        )
    else:
        await message.reply(
            f"ℹ️ <b>{message.from_user.mention}</b>,\n\n"
            f"<blockquote>Aapke paas koi active premium plan nahi hai.\n\n"
            f"Premium lene ke liye admin se contact karo.</blockquote>\n\n"
            f"Use /plan for more info."
        )


# ── /plan ─────────────────────────────────────────────────────────

@Bot.on_message(filters.command("plan") & filters.private)
async def cmd_plan(client: Bot, message: Message):
    await message.reply(
        f"⚜️ <b>Premium Membership Benefits</b>\n\n"
        f"<blockquote>"
        f"🚀 No Force Subscribe — koi channel join karne ki zaroorat nahi\n"
        f"🔗 No Link Shortener / Ads — direct file access\n"
        f"⚡ Fast Priority — sabse tez delivery"
        f"</blockquote>\n\n"
        f"📩 Premium lene ke liye admin se contact karo.\n\n"
        f"Apna status check karo: /myplan"
    )
