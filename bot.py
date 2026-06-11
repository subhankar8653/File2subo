import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from pyrogram.errors import FloodWait, UserNotParticipant
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, LOG_CHANNEL, LOGGER
from database import (
    add_user, user_exists, get_all_users, total_users,
    is_admin, add_admin, remove_admin, get_all_admins,
    is_banned, ban_user, unban_user,
    add_fsub, remove_fsub, get_fsub_channels,
    get_setting, set_setting
)
from helpers import encode, decode, make_link, make_batch_link, get_msg_id, get_messages, readable_size

log = LOGGER(__name__)

app = Client(
    "SuhaniFileBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def check_fsub(client: Client, user_id: int) -> list:
    """Returns list of channels user hasn't joined. Empty = all joined."""
    if user_id == OWNER_ID:
        return []
    channels = await get_fsub_channels()
    not_joined = []
    for ch_id in channels:
        try:
            member = await client.get_chat_member(ch_id, user_id)
            if member.status.name in ("BANNED", "LEFT"):
                not_joined.append(ch_id)
        except UserNotParticipant:
            not_joined.append(ch_id)
        except Exception:
            pass
    return not_joined

async def fsub_markup(client: Client, channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch_id in channels:
        try:
            chat = await client.get_chat(ch_id)
            link = f"https://t.me/{chat.username}" if chat.username else (await client.export_chat_invite_link(ch_id))
            buttons.append([InlineKeyboardButton(f"📢 {chat.title}", url=link)])
        except Exception:
            pass
    buttons.append([InlineKeyboardButton("✅ Joined? Click Here", callback_data="check_fsub")])
    return InlineKeyboardMarkup(buttons)

async def send_files(client: Client, user_id: int, msg_ids: list, protect: bool = False):
    """Send files from log channel to user."""
    msgs = await get_messages(client, LOG_CHANNEL, msg_ids)
    sent = 0
    for msg in msgs:
        if not msg or msg.empty:
            continue
        try:
            await msg.copy(
                chat_id=user_id,
                protect_content=protect,
            )
            sent += 1
            await asyncio.sleep(0.3)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            log.error(f"Send error to {user_id}: {e}")
    return sent

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /start
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.on_message(filters.command("start") & filters.private)
async def start(client: Client, message: Message):
    user_id = message.from_user.id

    # Register user
    if not await user_exists(user_id):
        await add_user(user_id)

    # Banned check
    if await is_banned(user_id):
        return await message.reply("🚫 <b>You are banned from using this bot.</b>")

    # Deep link handling
    if len(message.command) > 1:
        param = message.command[1]

        # Force sub check
        not_joined = await check_fsub(client, user_id)
        if not_joined:
            markup = await fsub_markup(client, not_joined)
            return await message.reply(
                "📢 <b>Please join our channels first to use this bot!</b>",
                reply_markup=markup
            )

        try:
            data = decode(param)
        except Exception:
            return await message.reply("❌ Invalid link.")

        protect = await get_setting("protect_content", False)

        # Single file: get-{msg_id}
        if data.startswith("get-"):
            msg_id = int(data.split("-")[1])
            wait = await message.reply("⏳ <b>Sending your file...</b>")
            sent = await send_files(client, user_id, [msg_id], protect)
            await wait.delete()
            if not sent:
                await message.reply("❌ File not found or deleted.")

        # Batch: batch-{first}-{last}
        elif data.startswith("batch-"):
            parts = data.split("-")
            first_id, last_id = int(parts[1]), int(parts[2])
            msg_ids = list(range(first_id, last_id + 1))
            wait = await message.reply(f"⏳ <b>Sending {len(msg_ids)} files...</b>")
            sent = await send_files(client, user_id, msg_ids, protect)
            await wait.delete()
            await message.reply(f"✅ <b>Sent {sent}/{len(msg_ids)} files.</b>")

        return

    # Normal /start
    me = await client.get_me()
    await message.reply(
        f"<b>👋 Welcome to {me.first_name}!\n\n"
        f"🔗 Send me a file link to get your files.\n"
        f"👑 Admins can generate links via /genlink or /batch.</b>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")
        ]]) if await is_admin(user_id) else None
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Force Sub callback
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.on_callback_query(filters.regex("^check_fsub$"))
async def check_fsub_cb(client: Client, query: CallbackQuery):
    not_joined = await check_fsub(client, query.from_user.id)
    if not_joined:
        await query.answer("❌ You haven't joined all channels yet!", show_alert=True)
    else:
        await query.answer("✅ Verified! Now send the link again.", show_alert=True)
        await query.message.delete()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AUTO LINK — File sent in LOG CHANNEL → auto generate link
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.on_message(filters.channel & (filters.document | filters.video | filters.audio | filters.photo))
async def auto_link(client: Client, message: Message):
    """When admin sends file to log channel → auto reply with link."""
    if message.chat.id != LOG_CHANNEL:
        return
    try:
        link = await make_link(client, message.id)
        await message.reply(
            f"🔗 <b>Link Generated!</b>\n\n"
            f"<code>{link}</code>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 Open Link", url=link)
            ]])
        )
    except Exception as e:
        log.error(f"Auto link error: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /genlink — Send file in private → get link
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.on_message(filters.command("genlink") & filters.private)
async def genlink(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return await message.reply("❌ <b>Admins only.</b>")

    await message.reply(
        "📎 <b>Forward or send the file/message to generate a link.</b>\n\n"
        "<i>Send /cancel to stop.</i>"
    )

    @app.on_message(filters.private & ~filters.command([]), group=10)
    async def get_file(c: Client, m: Message):
        if m.from_user.id != message.from_user.id:
            return
        if m.text and m.text == "/cancel":
            await m.reply("❌ Cancelled.")
            app.remove_handler(get_file_handler)
            return

        wait = await m.reply("⏳ Processing...")
        msg_id = await get_msg_id(c, m, LOG_CHANNEL)
        if not msg_id:
            await wait.edit("❌ Could not get message ID.")
            app.remove_handler(get_file_handler)
            return

        link = await make_link(c, msg_id)
        await wait.edit(
            f"✅ <b>Link Generated!</b>\n\n<blockquote><code>{link}</code></blockquote>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Open Link", url=link)]])
        )
        app.remove_handler(get_file_handler)

    from pyrogram.handlers import MessageHandler
    get_file_handler = MessageHandler(get_file, filters.private & ~filters.command([]))
    app.add_handler(get_file_handler, group=10)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /batch — Send 2 links (first & last) → batch link
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_batch_sessions = {}  # user_id -> first_msg_id

@app.on_message(filters.command("batch") & filters.private)
async def batch_start(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return await message.reply("❌ <b>Admins only.</b>")

    _batch_sessions[message.from_user.id] = {"step": "first"}
    await message.reply(
        "📦 <b>Batch Link Generator</b>\n\n"
        "Step 1️⃣: Forward or send the <b>FIRST</b> message of the batch.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="batch_cancel")
        ]])
    )

@app.on_callback_query(filters.regex("^batch_cancel$"))
async def batch_cancel_cb(client: Client, query: CallbackQuery):
    _batch_sessions.pop(query.from_user.id, None)
    await query.message.edit("<b>❌ Batch cancelled.</b>")

@app.on_message(filters.private & ~filters.command([
    "start", "genlink", "batch", "broadcast", "stats",
    "addadmin", "removeadmin", "ban", "unban", "addsub",
    "removesub", "protect", "cancel"
]))
async def batch_input(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        return
    if user_id not in _batch_sessions:
        return

    session = _batch_sessions.get(user_id, {})

    if isinstance(session, dict) and session.get("step") == "first":
        wait = await message.reply("⏳ Getting first message ID...")
        first_id = await get_msg_id(client, message, LOG_CHANNEL)
        if not first_id:
            return await wait.edit("❌ Could not get message ID. Try again.")
        _batch_sessions[user_id] = {"step": "last", "first_id": first_id}
        await wait.edit(
            f"✅ First message saved! (ID: <code>{first_id}</code>)\n\n"
            "Step 2️⃣: Now forward or send the <b>LAST</b> message of the batch.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="batch_cancel")
            ]])
        )
        return

    if isinstance(session, dict) and session.get("step") == "last":
        wait = await message.reply("⏳ Generating batch link...")
        last_id = await get_msg_id(client, message, LOG_CHANNEL)
        if not last_id:
            return await wait.edit("❌ Could not get message ID. Try again.")

        first_id = session["first_id"]
        if last_id < first_id:
            first_id, last_id = last_id, first_id

        link = await make_batch_link(client, first_id, last_id)
        count = last_id - first_id + 1
        _batch_sessions.pop(user_id, None)

        await wait.edit(
            f"✅ <b>Batch Link Generated!</b>\n"
            f"📁 Files: <b>{count}</b>\n\n"
            f"<blockquote><code>{link}</code></blockquote>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 Open Link", url=link)
            ]])
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADMIN COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.on_message(filters.command("addadmin") & filters.private)
async def cmd_addadmin(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Owner only.")
    if len(message.command) < 2:
        return await message.reply("Usage: /addadmin <user_id>")
    uid = int(message.command[1])
    await add_admin(uid)
    await message.reply(f"✅ <code>{uid}</code> added as admin.")

@app.on_message(filters.command("removeadmin") & filters.private)
async def cmd_removeadmin(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Owner only.")
    if len(message.command) < 2:
        return await message.reply("Usage: /removeadmin <user_id>")
    uid = int(message.command[1])
    await remove_admin(uid)
    await message.reply(f"✅ <code>{uid}</code> removed from admins.")

@app.on_message(filters.command("ban") & filters.private)
async def cmd_ban(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return await message.reply("❌ Admins only.")
    if len(message.command) < 2:
        return await message.reply("Usage: /ban <user_id>")
    uid = int(message.command[1])
    await ban_user(uid)
    await message.reply(f"🚫 <code>{uid}</code> banned.")

@app.on_message(filters.command("unban") & filters.private)
async def cmd_unban(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return await message.reply("❌ Admins only.")
    if len(message.command) < 2:
        return await message.reply("Usage: /unban <user_id>")
    uid = int(message.command[1])
    await unban_user(uid)
    await message.reply(f"✅ <code>{uid}</code> unbanned.")

@app.on_message(filters.command("addsub") & filters.private)
async def cmd_addsub(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return await message.reply("❌ Admins only.")
    if len(message.command) < 2:
        return await message.reply("Usage: /addsub <channel_id>")
    ch_id = int(message.command[1])
    await add_fsub(ch_id)
    await message.reply(f"✅ Force sub added for <code>{ch_id}</code>.")

@app.on_message(filters.command("removesub") & filters.private)
async def cmd_removesub(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return await message.reply("❌ Admins only.")
    if len(message.command) < 2:
        return await message.reply("Usage: /removesub <channel_id>")
    ch_id = int(message.command[1])
    await remove_fsub(ch_id)
    await message.reply(f"✅ Force sub removed for <code>{ch_id}</code>.")

@app.on_message(filters.command("protect") & filters.private)
async def cmd_protect(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return await message.reply("❌ Admins only.")
    current = await get_setting("protect_content", False)
    new_val = not current
    await set_setting("protect_content", new_val)
    status = "✅ ON" if new_val else "❌ OFF"
    await message.reply(f"🔒 Protect Content: <b>{status}</b>")

@app.on_message(filters.command("stats") & filters.private)
async def cmd_stats(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return await message.reply("❌ Admins only.")
    users = await total_users()
    admins = await get_all_admins()
    fsubs = await get_fsub_channels()
    protect = await get_setting("protect_content", False)
    await message.reply(
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: <b>{users}</b>\n"
        f"👑 Admins: <b>{len(admins)}</b>\n"
        f"📢 Force Sub Channels: <b>{len(fsubs)}</b>\n"
        f"🔒 Protect Content: <b>{'ON' if protect else 'OFF'}</b>"
    )

@app.on_message(filters.command("broadcast") & filters.private)
async def cmd_broadcast(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return await message.reply("❌ Admins only.")
    if not message.reply_to_message:
        return await message.reply("Reply to a message to broadcast it.")

    users = await get_all_users()
    wait = await message.reply(f"📣 Broadcasting to {len(users)} users...")

    success, failed = 0, 0
    for uid in users:
        try:
            await message.reply_to_message.copy(uid)
            success += 1
            await asyncio.sleep(0.05)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            failed += 1

    await wait.edit(
        f"✅ <b>Broadcast Done!</b>\n\n"
        f"✅ Success: <b>{success}</b>\n"
        f"❌ Failed: <b>{failed}</b>"
    )

@app.on_message(filters.command("admins") & filters.private)
async def cmd_admins(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Owner only.")
    admins = await get_all_admins()
    if not admins:
        return await message.reply("No admins yet.")
    text = "👑 <b>Admins:</b>\n\n"
    for uid in admins:
        text += f"• <code>{uid}</code>\n"
    await message.reply(text)
