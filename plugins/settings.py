import asyncio
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot import Bot
from config import ADMINS, OWNER_ID
from database.database import (
    get_setting, set_setting,
    add_fsub, remove_fsub, get_fsub_channels,
    get_fake_link, set_fake_link, remove_fake_link,
    get_fsub_request_mode, set_fsub_request_mode,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Helper — settings panel markup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def settings_text_and_markup(client):
    protect      = await get_setting("protect_content", False)
    auto_del     = await get_setting("auto_delete_time", 0)
    fsubs        = await get_fsub_channels()
    start_pic    = await get_setting("start_pic", "")
    start_msg    = await get_setting("start_msg", "")
    req_mode     = await get_fsub_request_mode()
    fake         = await get_fake_link()

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
        + f"\n📩 <b>Request Mode:</b> {'✅ ON' if req_mode else '❌ OFF'}"
        + f"\n🔗 <b>Fake Link:</b> {'✅ Set' if fake else '❌ Not set'}"
    )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"🔒 Protect: {'ON ✅' if protect else 'OFF ❌'}",
                callback_data="set_protect"
            ),
            InlineKeyboardButton(
                "⏱ Auto Delete",
                callback_data="set_autodel"
            ),
        ],
        [
            InlineKeyboardButton("📢 FSub Channels", callback_data="fsub_menu"),
            InlineKeyboardButton(
                f"📩 Request: {'ON ✅' if req_mode else 'OFF ❌'}",
                callback_data="set_reqmode"
            ),
        ],
        [
            InlineKeyboardButton(
                f"🔗 Fake Link: {'✅ Set' if fake else '❌ Not set'}",
                callback_data="fakelink_menu"
            ),
            InlineKeyboardButton("📋 List FSub", callback_data="set_listsub"),
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

@Bot.on_callback_query(filters.regex("^(set_|settings_refresh)"))
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FSub Menu & List
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def fsub_menu_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Add FSub", callback_data="set_addsub"),
            InlineKeyboardButton("🗑 Remove FSub", callback_data="set_removesub"),
        ],
        [
            InlineKeyboardButton("📋 List All FSub", callback_data="set_listsub"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="settings_back")],
    ])


@Bot.on_callback_query(filters.regex("^fsub_menu$"))
async def fsub_menu_cb(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Admins only!", show_alert=True)
    await query.message.edit_text(
        "📢 <b>FSub Channel Settings</b>\n\nKya karna hai?",
        reply_markup=await fsub_menu_markup(),
    )
    await query.answer()


@Bot.on_callback_query(filters.regex("^set_listsub$"))
async def listsub_cb(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Admins only!", show_alert=True)
    await query.answer()
    fsubs = await get_fsub_channels()
    if not fsubs:
        return await query.message.edit_text(
            "📢 <b>Koi FSub channel set nahi hai.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="fsub_menu")]]),
        )
    lines = ["<b>📢 Force Sub Channels:</b>\n"]
    for i, ch_id in enumerate(fsubs, 1):
        try:
            chat = await client.get_chat(ch_id)
            link = f"https://t.me/{chat.username}" if chat.username else "—"
            lines.append(f"{i}. <b>{chat.title}</b>  🆔 <code>{ch_id}</code>  🔗 {link}")
        except Exception:
            lines.append(f"{i}. <code>{ch_id}</code> (info fetch nahi hua)")
    lines.append(f"\n<b>Total:</b> {len(fsubs)}")
    await query.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="fsub_menu")]]),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Request Mode Toggle
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_callback_query(filters.regex("^set_reqmode$"))
async def reqmode_cb(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Admins only!", show_alert=True)
    current = await get_fsub_request_mode()
    await set_fsub_request_mode(not current)
    text, markup = await settings_text_and_markup(client)
    await query.message.edit_text(text, reply_markup=markup)
    status = "ON ✅" if not current else "OFF ❌"
    await query.answer(f"📩 Request Mode: {status}", show_alert=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Fake Link Menu
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def fakelink_menu_markup():
    fake = await get_fake_link()
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Set Fake Link", callback_data="set_fakelink_set"),
            InlineKeyboardButton("👁 View", callback_data="set_fakelink_view"),
        ],
        [
            InlineKeyboardButton("🗑 Remove", callback_data="set_fakelink_remove"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="settings_back")],
    ])


@Bot.on_callback_query(filters.regex("^fakelink_menu$"))
async def fakelink_menu_cb(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Admins only!", show_alert=True)
    fake = await get_fake_link()
    status = f"<b>Current:</b> <code>{fake['button_text']}</code> → <code>{fake['url']}</code>" if fake else "<i>Koi fake link set nahi hai.</i>"
    await query.message.edit_text(
        f"🔗 <b>Fake Link Settings</b>\n\n{status}",
        reply_markup=await fakelink_menu_markup(),
    )
    await query.answer()


@Bot.on_callback_query(filters.regex("^set_fakelink_view$"))
async def fakelink_view_cb(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Admins only!", show_alert=True)
    fake = await get_fake_link()
    if fake:
        await query.answer(
            f"Text: {fake['button_text']}\nURL: {fake['url']}",
            show_alert=True,
        )
    else:
        await query.answer("❌ Koi fake link set nahi hai!", show_alert=True)


@Bot.on_callback_query(filters.regex("^set_fakelink_remove$"))
async def fakelink_remove_cb(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Admins only!", show_alert=True)
    result = await remove_fake_link()
    if result:
        await query.answer("✅ Fake link hata diya!", show_alert=True)
    else:
        await query.answer("❌ Koi fake link set nahi tha.", show_alert=True)
    # Refresh fake link menu
    fake = await get_fake_link()
    status = f"<b>Current:</b> <code>{fake['button_text']}</code> → <code>{fake['url']}</code>" if fake else "<i>Koi fake link set nahi hai.</i>"
    await query.message.edit_text(
        f"🔗 <b>Fake Link Settings</b>\n\n{status}",
        reply_markup=await fakelink_menu_markup(),
    )


@Bot.on_callback_query(filters.regex("^set_fakelink_set$"))
async def fakelink_set_cb(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Admins only!", show_alert=True)
    await query.answer()
    ask = await query.message.reply(
        "🔗 <b>Fake Link set karo</b>\n\n"
        "Format: <code>URL Button Text</code>\n"
        "Example: <code>https://t.me/mychannel Join Sponsor</code>\n\n"
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
    if resp.text.strip() == "/cancel":
        return await resp.delete()

    parts = resp.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await resp.reply("❌ Galat format! URL aur Button Text dono chahiye.")

    url, btn_text = parts[0], parts[1]
    if not url.startswith(("http://", "https://", "t.me/")):
        return await resp.reply("❌ Valid URL dalo (http/https/t.me se shuru hona chahiye).")

    success = await set_fake_link(url, btn_text)
    if success:
        await resp.reply(
            f"✅ <b>Fake Link set!</b>\n\n"
            f"<b>Button:</b> <code>{btn_text}</code>\n"
            f"<b>URL:</b> <code>{url}</code>"
        )
    else:
        await resp.reply("❌ Error! Save nahi hua. Dobara try karo.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Back to Main Settings
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_callback_query(filters.regex("^settings_back$"))
async def settings_back_cb(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Admins only!", show_alert=True)
    text, markup = await settings_text_and_markup(client)
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer()
