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
from urllib.parse import quote

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot import Bot
from config import ADMINS, LOG_CHANNEL
from helper_func import parse_duration
from database.database import (
    has_premium_access, get_premium_expiry,
    add_premium, remove_premium, get_all_premium_users,
)

log = logging.getLogger(__name__)

# ── Premium purchase contact ────────────────────────────────────────
# Premium kharidne ke liye user is account ko message karega.
# "Buy This Plan" pe click karte hi plan ka naam/duration/price prefilled
# message ke saath is account ko bhej diya jaata hai.
PREMIUM_CONTACT_USERNAME = "Sbanime_Premium_robot"
PREMIUM_CONTACT_URL = f"https://t.me/{PREMIUM_CONTACT_USERNAME}"


def _buy_url(text: str) -> str:
    """t.me deep link with a prefilled message to the premium contact."""
    return f"{PREMIUM_CONTACT_URL}?text={quote(text)}"


# ── Plans data ────────────────────────────────────────────────────
PLANS = {
    "bronze": {
        "emoji": "🥉",
        "name": "Bronze Plan",
        "duration": "7 Days",
        "days": 7,
        "price": "₹10",
        "prev": "other",
        "next": "silver",
    },
    "silver": {
        "emoji": "🥈",
        "name": "Silver Plan",
        "duration": "15 Days",
        "days": 15,
        "price": "₹20",
        "prev": "bronze",
        "next": "gold",
    },
    "gold": {
        "emoji": "🥇",
        "name": "Gold Plan",
        "duration": "30 Days",
        "days": 30,
        "price": "₹40",
        "prev": "silver",
        "next": "platinum",
    },
    "platinum": {
        "emoji": "🏅",
        "name": "Platinum Plan",
        "duration": "45 Days",
        "days": 45,
        "price": "₹55",
        "prev": "gold",
        "next": "diamond",
    },
    "diamond": {
        "emoji": "💎",
        "name": "Diamond Plan",
        "duration": "60 Days",
        "days": 60,
        "price": "₹75",
        "prev": "platinum",
        "next": "other",
    },
    "other": {
        "emoji": "🎁",
        "name": "Other / Custom Plan",
        "duration": "Customised Days",
        "days": None,
        "price": "According to days you choose",
        "prev": "diamond",
        "next": "bronze",
    },
}


# ── Plan auto-detect (for /addpremium) ──────────────────────────────

def _match_plan(seconds: int) -> str | None:
    """Duration (seconds) ko PLANS ke 'days' se match karo. No match → None (custom)."""
    days = seconds / 86400
    for key, p in PLANS.items():
        if p["days"] is not None and abs(days - p["days"]) < 0.01:
            return key
    return None




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

    # ── Auto-detect plan from duration ────────────────────────────
    plan_key = _match_plan(seconds)
    if plan_key:
        plan_label = PLANS[plan_key]["name"]
        plan_line  = f"📦 Plan: <b>{plan_label}</b>\n"
    else:
        plan_label = "Custom Plan"
        plan_line  = f"📦 Plan: <b>{plan_label}</b> (custom duration)\n"

    await message.reply(
        f"✅ <b>Premium Added Successfully!</b>\n\n"
        f"👤 User: {mention}\n"
        f"🆔 User ID: <code>{user_id}</code>\n"
        f"{plan_line}"
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
                f"Aapka <b>{plan_label}</b> successfully activate ho gaya hai! ✅\n\n"
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
                    f"{plan_line}"
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
            f"Premium lene ke liye neeche button par click karo.</blockquote>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚜️ View Plans", callback_data="plan_menu"),
            ], [
                InlineKeyboardButton("💸 Contact To Buy", url=_buy_url("Hi, I'm interested in Premium Fast Download")),
            ]])
        )


# ── /plan — Main premium plans menu ─────────────────────────────────

@Bot.on_message(filters.command("plan") & filters.private)
async def cmd_plan(client: Bot, message: Message):
    await message.reply(
        _premium_overview_text(message.from_user.mention),
        reply_markup=_main_plan_menu(),
        disable_web_page_preview=True,
    )


def _premium_overview_text(mention: str) -> str:
    return (
        f"👋 <b>Hey {mention},</b>\n\n"
        f"<blockquote>🎁 <b>Premium Membership — Suhani Bots</b>\n"
        f"Sirf ₹40/30 days | All bots included!</blockquote>\n\n"
        f"<b>🤖 Bots Covered:</b>\n"
        f"┌ <b>@SenpaiSyncbot</b> — Anime link bot\n"
        f"│ No shortner · No FSub · Direct channel link\n"
        f"│\n"
        f"├ <b>@Get_Suhani_bot</b> — Anime file bot\n"
        f"│ No shortner · No FSub · Direct files\n"
        f"│ Online watch · Media info · Fast download\n"
        f"│\n"
        f"├ <b>@Suhani_filter_bot</b> — Anime search bot\n"
        f"│ Search anime in DM · AI chat in DM\n"
        f"│\n"
        f"├ <b>@Miss_suhani_bot</b> — Group protection + AI\n"
        f"│ Use in your group · AI feature included\n"
        f"│\n"
        f"├ <b>@My_Suhani_bot</b> — Movie search bot\n"
        f"│ No shortner · No FSub · Direct files\n"
        f"│ Online watch · Media info · Fast support\n"
        f"│\n"
        f"└ <b>🔞 Hanime Private Channel</b>\n"
        f"  No shortner · Direct videos · Contact to get access\n\n"
        f"<b>🎯 Extra Benefits:</b>\n"
        f"⭐ Koi bhi anime/movie request karo — admin puri koshish karega\n"
        f"⭐ Future new bots ka premium bhi is plan mein aayega\n"
        f"⭐ Fast support via @Sbanime_Premium_robot\n\n"
        f"📌 Plan details ke liye neeche buttons tap karo.\n"
        f"📌 Active plan check karo: /myplan"
    )


def _main_plan_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{PLANS['bronze']['emoji']} Bronze", callback_data="plan_bronze"),
            InlineKeyboardButton(f"{PLANS['silver']['emoji']} Silver", callback_data="plan_silver"),
        ],
        [
            InlineKeyboardButton(f"{PLANS['gold']['emoji']} Gold", callback_data="plan_gold"),
            InlineKeyboardButton(f"{PLANS['platinum']['emoji']} Platinum", callback_data="plan_platinum"),
        ],
        [
            InlineKeyboardButton(f"{PLANS['diamond']['emoji']} Diamond", callback_data="plan_diamond"),
            InlineKeyboardButton(f"{PLANS['other']['emoji']} Other", callback_data="plan_other"),
        ],
        [
            InlineKeyboardButton("💸 Contact To Buy Premium", url=_buy_url("Hi, I'm interested in Premium Fast Download")),
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="plan_close"),
        ],
    ])


def _plan_detail_text(key: str, mention: str) -> str:
    p = PLANS[key]
    if key == "other":
        return (
            f"👋 <b>Hey {mention},</b>\n\n"
            f"{p['emoji']} <u><b>{p['name']}</b></u>\n"
            f"⏰ Duration: <b>{p['duration']}</b>\n"
            f"💸 Price: <b>{p['price']}</b>\n\n"
            f"🏆 Want a custom plan apart from the above? Message the contact below directly.\n\n"
            f"📌 Use /plan to see all plans again.\n"
            f"📌 Check your active plan: /myplan"
        )
    return (
        f"👋 <b>Hey {mention},</b>\n\n"
        f"{p['emoji']} <u><b>{p['name']}</b></u>\n"
        f"⏰ Duration: <b>{p['duration']}</b>\n"
        f"💸 Price: <b>{p['price']}</b>\n\n"
        f"📌 Use /plan to see all plans again.\n"
        f"📌 Check your active plan: /myplan"
    )


def _plan_detail_menu(key: str) -> InlineKeyboardMarkup:
    p = PLANS[key]
    if key == "other":
        buy_text = "Hi, I'm interested in a Custom Premium Plan - Fast Download"
    else:
        buy_text = f"Hi, I'm interested in Premium {p['name']} ({p['duration']} - {p['price']}) - Fast Download"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 Buy This Plan", url=_buy_url(buy_text))],
        [
            InlineKeyboardButton("⋞ Back", callback_data=f"plan_{p['prev']}"),
            InlineKeyboardButton("📋 All Plans", callback_data="plan_menu"),
            InlineKeyboardButton("Next ⋟", callback_data=f"plan_{p['next']}"),
        ],
    ])


# ── Plan callbacks ───────────────────────────────────────────────

@Bot.on_callback_query(filters.regex(r"^plan_(bronze|silver|gold|platinum|diamond|other)$"))
async def cb_plan_detail(client: Bot, query: CallbackQuery):
    key = query.data.split("_", 1)[1]
    await query.message.edit_text(
        _plan_detail_text(key, query.from_user.mention),
        reply_markup=_plan_detail_menu(key),
        disable_web_page_preview=True,
    )
    await query.answer()


@Bot.on_callback_query(filters.regex("^plan_menu$"))
async def cb_plan_menu(client: Bot, query: CallbackQuery):
    await query.message.edit_text(
        _premium_overview_text(query.from_user.mention),
        reply_markup=_main_plan_menu(),
        disable_web_page_preview=True,
    )
    await query.answer()


@Bot.on_callback_query(filters.regex("^plan_close$"))
async def cb_plan_close(client: Bot, query: CallbackQuery):
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.answer()

