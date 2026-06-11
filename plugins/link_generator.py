import pyromod.listen
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot import Bot
from config import ADMINS
from helper_func import encode, get_message_id


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /genlink — single file
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("genlink"))
async def link_generator(client: Client, message: Message):
    while True:
        try:
            channel_message = await client.ask(
                chat_id=message.from_user.id,
                text="📎 <b>Forward a message from DB Channel</b> (with quotes)\nor send the DB channel post link.",
                filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                timeout=60,
            )
        except Exception:
            return

        msg_id = await get_message_id(client, channel_message)
        if msg_id:
            break
        await channel_message.reply(
            "❌ This message is not from the DB Channel. Try again.",
            quote=True,
        )

    base64_string = await encode(f"get-{msg_id * abs(client.db_channel.id)}")
    link = f"https://t.me/{client.username}?start={base64_string}"
    reply_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔁 Share URL", url=f"https://telegram.me/share/url?url={link}")
    ]])
    await channel_message.reply_text(
        f"<b>✅ Here is your link</b>\n\n<code>{link}</code>",
        quote=True,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /batch — range of files
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("batch"))
async def batch(client: Client, message: Message):
    # Step 1: First message
    while True:
        try:
            first_message = await client.ask(
                chat_id=message.from_user.id,
                text="📦 <b>Batch Link Generator</b>\n\nStep 1️⃣: Forward the <b>FIRST</b> message from DB Channel\nor send its link.",
                filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                timeout=60,
            )
        except Exception:
            return

        f_msg_id = await get_message_id(client, first_message)
        if f_msg_id:
            break
        await first_message.reply("❌ Not from DB Channel. Try again.", quote=True)

    # Step 2: Last message
    while True:
        try:
            second_message = await client.ask(
                chat_id=message.from_user.id,
                text="Step 2️⃣: Now forward the <b>LAST</b> message from DB Channel\nor send its link.",
                filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                timeout=60,
            )
        except Exception:
            return

        s_msg_id = await get_message_id(client, second_message)
        if s_msg_id:
            break
        await second_message.reply("❌ Not from DB Channel. Try again.", quote=True)

    string = f"get-{f_msg_id * abs(client.db_channel.id)}-{s_msg_id * abs(client.db_channel.id)}"
    base64_string = await encode(string)
    link = f"https://t.me/{client.username}?start={base64_string}"
    count = abs(s_msg_id - f_msg_id) + 1

    reply_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔁 Share URL", url=f"https://telegram.me/share/url?url={link}")
    ]])
    await second_message.reply_text(
        f"<b>✅ Batch Link Generated!</b>\n📁 Files: <b>{count}</b>\n\n<code>{link}</code>",
        quote=True,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )
