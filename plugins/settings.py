import asyncio
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot import Bot
from config import ADMINS, OWNER_ID
from database.database import (
    get_setting, set_setting,
    add_fsub, remove_fsub, get_fsub_channels,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Helper — settings panel markup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def settings_text_and_markup(client):
    protect   = await get_setting("protect_content", False)
    auto_del  = await get_setting("auto_delete_time", 0)
    fsubs     = await get_fsub_channels()
    start_pic = await get_setting("start_pic", "")
    start_msg = await get_setting("start_msg", "")

    # Force sub channels list
    fsub_list = ""
    for ch_id in fsubs:
        try:
            chat = await client.get_chat(ch_id)
            fsub_list += f"\n  • {chat.title} (<code>{ch_id}</code>)"
        except Exception:
            fsub_list += f"\n  • <code>{ch_id}</code>"

    text = (
        "⚙️ <b>Bot Settings</b>\n\n"
        f"🔒 <b>Protect Content:</b> {'✅ ON' if protect else '❌ OFF'}\n"
        f"⏱ <b>Auto Delete:</b> {'❌ OFF' if not auto_del else f'✅ {auto_del}s'}\n"
        f"🖼 <b>Start Pic:</b> {'✅ Set' if start_pic else '❌ Not set'}\n"
        f"💬 <b>Start Message:</b> {'✅ Custom' if start_msg else '⚙️ Default'}\n"
        f"📢 <b>Force Sub Channels:</b> {len(fsubs)}"
        + (fsub_list if fsubs else " (none)")
    )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"🔒 Protect: {'ON ✅' if protect else 'OFF ❌'}",
                callback_data="set_protect"
            ),
            InlineKeyboardButton(
                f"⏱ Auto Delete",
                callback_data="set_autodel"
            ),
        ],
        [
            InlineKeyboardButton("📢 Add FSub Channel", callback_data="set_addsub"),
            InlineKeyboardButton("🗑 Remove FSub", callback_data="set_removesub"),
        ],
        [
            InlineKeyboardButton("🖼 Set Start Pic", callback_data="set_startpic"),
            InlineKeyboardButton("💬 Set Start Msg", callback_data="set_startmsg"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="settings_refresh"),
            InlineKeyboardButton("🔒 Close", callback_data="close"),
        ],
    ])

    return text, markup


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /settings command
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_message(filters.command("settings") & filters.private & filters.user(ADMINS))
async def cmd_settings(client, message: Message):
    text, markup = await settings_text_and_markup(client)
    await message.reply(text, reply_markup=markup)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Settings callbacks
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_callback_query(filters.regex("^set_") | filters.regex("^settings_refresh$"))
async def settings_cb(client, query: CallbackQuery):
    # Only admins
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Admins only!", show_alert=True)

    data = query.data

    # ── Refresh ───────────────────────────────────────────────────
    if data == "settings_refresh":
        text, markup = await settings_text_and_markup(client)
        await query.message.edit_text(text, reply_markup=markup)
        return await query.answer("✅ Refreshed!")

    # ── Protect toggle ────────────────────────────────────────────
    if data == "set_protect":
        current = await get_setting("protect_content", False)
        await set_setting("protect_content", not current)
        text, markup = await settings_text_and_markup(client)
        await query.message.edit_text(text, reply_markup=markup)
        status = "ON ✅" if not current else "OFF ❌"
        return await query.answer(f"🔒 Protect Content: {status}", show_alert=True)

    # ── Auto Delete ───────────────────────────────────────────────
    if data == "set_autodel":
        await query.answer()
        ask = await query.message.reply(
            "⏱ <b>Auto Delete Time set karo</b>\n\n"
            "Seconds mein number bhejo (e.g. <code>300</code> = 5 min)\n"
            "<code>0</code> bhejo disable karne ke liye.\n\n"
            "/cancel karo quit karne ke liye."
        )
        try:
            resp = await client.listen(
                chat_id=query.from_user.id,
                filters=filters.text,
                timeout=60,
            )
        except asyncio.TimeoutError:
            await ask.delete()
            return

        await ask.delete()
        if resp.text == "/cancel":
            return await resp.delete()

        try:
            val = int(resp.text.strip())
            await set_setting("auto_delete_time", val)
            await resp.reply(
                f"✅ Auto Delete: <b>{'OFF' if val == 0 else f'{val}s'}</b>"
            )
        except ValueError:
            await resp.reply("❌ Sirf number bhejo (e.g. 300)")
        return

    # ── Add FSub ──────────────────────────────────────────────────
    if data == "set_addsub":
        await query.answer()
        ask = await query.message.reply(
            "📢 <b>Force Sub Channel add karo</b>\n\n"
            "Channel ID bhejo (e.g. <code>-1001234567890</code>)\n"
            "Bot ko us channel ka admin hona chahiye.\n\n"
            "/cancel karo quit karne ke liye."
        )
        try:
            resp = await client.listen(
                chat_id=query.from_user.id,
                filters=filters.text,
                timeout=60,
            )
        except asyncio.TimeoutError:
            await ask.delete()
            return

        await ask.delete()
        if resp.text == "/cancel":
            return await resp.delete()

        try:
            ch_id = int(resp.text.strip())
            # Verify bot is admin
            chat = await client.get_chat(ch_id)
            await add_fsub(ch_id)
            # Cache invite link
            try:
                link = chat.invite_link
                if not link:
                    await client.export_chat_invite_link(ch_id)
                client.invitelink = (await client.get_chat(ch_id)).invite_link
            except Exception:
                pass
            await resp.reply(f"✅ Force sub added: <b>{chat.title}</b> (<code>{ch_id}</code>)")
        except ValueError:
            await resp.reply("❌ Valid channel ID bhejo (e.g. -1001234567890)")
        except Exception as e:
            await resp.reply(f"❌ Error: <code>{e}</code>\nBot ko channel ka admin banao pehle.")
        return

    # ── Remove FSub ───────────────────────────────────────────────
    if data == "set_removesub":
        fsubs = await get_fsub_channels()
        if not fsubs:
            return await query.answer("❌ Koi FSub channel nahi hai!", show_alert=True)

        await query.answer()
        # Build list
        lines = []
        for ch_id in fsubs:
            try:
                chat = await client.get_chat(ch_id)
                lines.append(f"• {chat.title}: <code>{ch_id}</code>")
            except Exception:
                lines.append(f"• <code>{ch_id}</code>")

        ask = await query.message.reply(
            "🗑 <b>Kaun sa FSub channel hatana hai?</b>\n\n"
            + "\n".join(lines)
            + "\n\nChannel ID bhejo.\n/cancel karo quit karne ke liye."
        )
        try:
            resp = await client.listen(
                chat_id=query.from_user.id,
                filters=filters.text,
                timeout=60,
            )
        except asyncio.TimeoutError:
            await ask.delete()
            return

        await ask.delete()
        if resp.text == "/cancel":
            return await resp.delete()

        try:
            ch_id = int(resp.text.strip())
            await remove_fsub(ch_id)
            await resp.reply(f"✅ FSub removed: <code>{ch_id}</code>")
        except ValueError:
            await resp.reply("❌ Valid channel ID bhejo")
        return

    # ── Set Start Pic ─────────────────────────────────────────────
    if data == "set_startpic":
        await query.answer()
        ask = await query.message.reply(
            "🖼 <b>Start Pic set karo</b>\n\n"
            "Ek photo bhejo ya photo ka URL bhejo.\n"
            "<code>remove</code> bhejo hatane ke liye.\n"
            "/cancel karo quit karne ke liye."
        )
        try:
            resp = await client.listen(
                chat_id=query.from_user.id,
                filters=filters.photo | filters.text,
                timeout=60,
            )
        except asyncio.TimeoutError:
            await ask.delete()
            return

        await ask.delete()
        if resp.text == "/cancel":
            return await resp.delete()

        if resp.text and resp.text.lower() == "remove":
            await set_setting("start_pic", "")
            await resp.reply("✅ Start pic removed.")
        elif resp.photo:
            await set_setting("start_pic", resp.photo.file_id)
            await resp.reply("✅ Start pic set!")
        elif resp.text:
            await set_setting("start_pic", resp.text.strip())
            await resp.reply("✅ Start pic URL set!")
        return

    # ── Set Start Message ─────────────────────────────────────────
    if data == "set_startmsg":
        await query.answer()
        ask = await query.message.reply(
            "💬 <b>Start Message set karo</b>\n\n"
            "Naya welcome message bhejo.\n"
            "Yeh variables use kar sakte ho:\n"
            "<code>{first}</code> — first name\n"
            "<code>{last}</code> — last name\n"
            "<code>{mention}</code> — mention\n"
            "<code>{id}</code> — user ID\n\n"
            "<code>remove</code> bhejo default pe wapas aane ke liye.\n"
            "/cancel karo quit karne ke liye."
        )
        try:
            resp = await client.listen(
                chat_id=query.from_user.id,
                filters=filters.text,
                timeout=120,
            )
        except asyncio.TimeoutError:
            await ask.delete()
            return

        await ask.delete()
        if resp.text == "/cancel":
            return await resp.delete()

        if resp.text.lower() == "remove":
            await set_setting("start_msg", "")
            await resp.reply("✅ Start message reset to default.")
        else:
            await set_setting("start_msg", resp.text)
            await resp.reply("✅ Start message set!")
        return
