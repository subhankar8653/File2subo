from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot import Bot
from config import ADMINS, OWNER_ID
from database.database import (
    add_admin, remove_admin, get_all_admins,
    ban_user, unban_user,
    get_fsub_channels,
    get_setting, set_setting, total_users,
)
from helper_func import get_readable_time
from datetime import datetime


@Bot.on_message(filters.command("addadmin") & filters.private & filters.user(OWNER_ID))
async def cmd_addadmin(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /addadmin <user_id>")
    uid = int(message.command[1])
    await add_admin(uid)
    await message.reply(f"✅ <code>{uid}</code> added as admin.")


@Bot.on_message(filters.command("removeadmin") & filters.private & filters.user(OWNER_ID))
async def cmd_removeadmin(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /removeadmin <user_id>")
    uid = int(message.command[1])
    await remove_admin(uid)
    await message.reply(f"✅ <code>{uid}</code> removed from admins.")


@Bot.on_message(filters.command("ban") & filters.private & filters.user(ADMINS))
async def cmd_ban(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /ban <user_id>")
    uid = int(message.command[1])
    await ban_user(uid)
    await message.reply(f"🚫 <code>{uid}</code> banned.")


@Bot.on_message(filters.command("unban") & filters.private & filters.user(ADMINS))
async def cmd_unban(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /unban <user_id>")
    uid = int(message.command[1])
    await unban_user(uid)
    await message.reply(f"✅ <code>{uid}</code> unbanned.")



@Bot.on_message(filters.command("protect") & filters.private & filters.user(ADMINS))
async def cmd_protect(client, message: Message):
    current = await get_setting("protect_content", False)
    new_val = not current
    await set_setting("protect_content", new_val)
    status = "✅ ON" if new_val else "❌ OFF"
    await message.reply(f"🔒 Protect Content: <b>{status}</b>")


@Bot.on_message(filters.command("stats") & filters.private & filters.user(ADMINS))
async def cmd_stats(client: Bot, message: Message):
    now = datetime.now()
    delta = now - client.uptime
    uptime = get_readable_time(int(delta.total_seconds()))
    users = await total_users()
    admins = await get_all_admins()
    fsubs = await get_fsub_channels()
    protect = await get_setting("protect_content", False)
    await message.reply(
        f"📊 <b>Bot Statistics</b>\n\n"
        f"⏱ Uptime: <b>{uptime}</b>\n"
        f"👥 Users: <b>{users}</b>\n"
        f"👑 Admins: <b>{len(admins)}</b>\n"
        f"📢 Force Sub Channels: <b>{len(fsubs)}</b>\n"
        f"🔒 Protect Content: <b>{'ON' if protect else 'OFF'}</b>"
    )
