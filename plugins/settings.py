import asyncio
import re
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot import Bot
from config import ADMINS, OWNER_ID
from database.database import (
    get_setting, set_setting,
    add_fsub, remove_fsub, get_fsub_channels,
    get_fake_link, set_fake_link, remove_fake_link,
    get_fsub_request_mode, set_fsub_request_mode,
    get_fsub_channel_name, set_fsub_channel_name, clear_fsub_channel_name,
    get_shortener_settings, set_bot_config, get_bot_config,
    get_tutorial_status, toggle_tutorial,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Helper — settings panel markup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def settings_text_and_markup(client):
    protect  = await get_setting("protect_content", False)
    auto_del = await get_setting("auto_delete_time", 0)
    fsubs    = await get_fsub_channels()
    start_pic = await get_setting("start_pic", "")
    start_msg = await get_setting("start_msg", "")
    req_mode  = await get_fsub_request_mode()
    fake      = await get_fake_link()

    # Shortener status
    s = await get_shortener_settings()
    shn_status = "✅ ON" if s["enabled"] else "❌ OFF"

    # Tutorial status
    fsub_tut   = await get_tutorial_status("fsub")
    shn_tut    = await get_tutorial_status("shortener")
    fsub_tut_status = "✅" if fsub_tut["enabled"] else "❌"
    shn_tut_status  = "✅" if shn_tut["enabled"] else "❌"

    fsub_list = ""
    for ch_id in fsubs:
        try:
            chat = await client.get_chat(ch_id)
            custom_name = await get_fsub_channel_name(ch_id)
            name_display = f" [{custom_name}]" if custom_name else ""
            fsub_list += f"\n  • {chat.title}{name_display} (<code>{ch_id}</code>)"
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
        + f"\n⚡ <b>Shortener:</b> {shn_status}"
        + f"\n📹 <b>Tutorials:</b> FSub {fsub_tut_status}  |  Shortener {shn_tut_status}"
    )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"🔒 Protect: {'ON ✅' if protect else 'OFF ❌'}",
                callback_data="set_protect"
            ),
            InlineKeyboardButton("⏱ Auto Delete", callback_data="set_autodel"),
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
            InlineKeyboardButton("⚡ Shortener", callback_data="shortener_menu"),
            InlineKeyboardButton("📹 Tutorials", callback_data="tutorial_menu"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="settings_refresh"),
            InlineKeyboardButton("🔒 Close", callback_data="close"),
        ],
    ])

    return text, markup


async def fsub_menu_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add FSub", callback_data="set_addsub"),
            InlineKeyboardButton("🗑 Remove FSub", callback_data="set_removesub"),
        ],
        [
            InlineKeyboardButton("✏️ Rename Button", callback_data="set_rename_fsub"),
            InlineKeyboardButton("📋 List All FSub", callback_data="set_listsub"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="settings_back")],
    ])


async def fakelink_menu_markup():
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


async def shortener_menu_markup():
    s = await get_shortener_settings()
    cfg = await get_bot_config()
    verify_sec = cfg.get("verify_premium_seconds", 86400)
    h = verify_sec // 3600
    m = (verify_sec % 3600) // 60
    dur = f"{h}h" if m == 0 else f"{h}h {m}m"
    api_display = (s["api"][:8] + "...") if s["api"] else "❌ Not set"
    site_display = s["website"] or "❌ Not set"
    status_btn = "🔴 Turn OFF" if s["enabled"] else "🟢 Turn ON"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔑 Set API + Site", callback_data="shn_set"),
            InlineKeyboardButton(status_btn, callback_data="shn_toggle_cb"),
        ],
        [
            InlineKeyboardButton("⏰ Set Verify Time", callback_data="shn_settime"),
            InlineKeyboardButton("🗑 Remove Shortener", callback_data="shn_remove"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="settings_back")],
    ])


async def tutorial_menu_markup():
    fsub_tut = await get_tutorial_status("fsub")
    shn_tut  = await get_tutorial_status("shortener")
    fsub_btn = "🔴 FSub Tutorial OFF" if fsub_tut["enabled"] else "🟢 FSub Tutorial ON"
    shn_btn  = "🔴 Shortener Tutorial OFF" if shn_tut["enabled"] else "🟢 Shortener Tutorial ON"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📹 Set FSub Video", callback_data="tut_set_fsub"),
            InlineKeyboardButton("📹 Set Shortener Video", callback_data="tut_set_shn"),
        ],
        [
            InlineKeyboardButton(fsub_btn, callback_data="tut_toggle_fsub"),
            InlineKeyboardButton(shn_btn, callback_data="tut_toggle_shn"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="settings_back")],
    ])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /settings command
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_message(filters.command("settings") & filters.private & filters.user(ADMINS))
async def cmd_settings(client, message: Message):
    text, markup = await settings_text_and_markup(client)
    await message.reply(text, reply_markup=markup)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ALL Settings Callbacks — Single Handler
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_callback_query(filters.regex(
    r"^(settings_refresh|settings_back|set_protect|set_autodel|set_addsub|set_removesub"
    r"|set_startpic|set_startmsg|set_listsub|set_reqmode"
    r"|fsub_menu|fakelink_menu|set_fakelink_set|set_fakelink_view|set_fakelink_remove"
    r"|set_rename_fsub"
    r"|shortener_menu|shn_set|shn_toggle_cb|shn_settime|shn_remove"
    r"|tutorial_menu|tut_set_fsub|tut_set_shn|tut_toggle_fsub|tut_toggle_shn)$"
))
async def settings_cb(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Admins only!", show_alert=True)

    data = query.data

    # ── Refresh ─────────────────────────────────────────────────
    if data == "settings_refresh":
        text, markup = await settings_text_and_markup(client)
        await query.message.edit_text(text, reply_markup=markup)
        return await query.answer("✅ Refreshed!")

    # ── Back to main settings ───────────────────────────────────
    if data == "settings_back":
        text, markup = await settings_text_and_markup(client)
        await query.message.edit_text(text, reply_markup=markup)
        return await query.answer()

    # ── Protect toggle ──────────────────────────────────────────
    if data == "set_protect":
        current = await get_setting("protect_content", False)
        await set_setting("protect_content", not current)
        text, markup = await settings_text_and_markup(client)
        await query.message.edit_text(text, reply_markup=markup)
        status = "ON ✅" if not current else "OFF ❌"
        return await query.answer(f"🔒 Protect Content: {status}", show_alert=True)

    # ── Auto Delete ─────────────────────────────────────────────
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
        if resp.text.strip() == "/cancel":
            return await resp.delete()
        try:
            val = int(resp.text.strip())
            await set_setting("auto_delete_time", val)
            await resp.reply(f"✅ Auto Delete: <b>{'OFF' if val == 0 else f'{val}s'}</b>")
        except ValueError:
            await resp.reply("❌ Sirf number bhejo (e.g. 300)")
        return

    # ── FSub Menu ───────────────────────────────────────────────
    if data == "fsub_menu":
        await query.message.edit_text(
            "📢 <b>FSub Channel Settings</b>\n\nKya karna hai?",
            reply_markup=await fsub_menu_markup(),
        )
        return await query.answer()

    # ── Add FSub ────────────────────────────────────────────────
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
        if resp.text.strip() == "/cancel":
            return await resp.delete()
        try:
            ch_id = int(resp.text.strip())
            chat = await client.get_chat(ch_id)
            await add_fsub(ch_id)
            try:
                link = chat.invite_link
                if not link:
                    await client.export_chat_invite_link(ch_id)
            except Exception:
                pass
            await resp.reply(f"✅ Force sub added: <b>{chat.title}</b> (<code>{ch_id}</code>)")
        except ValueError:
            await resp.reply("❌ Valid channel ID bhejo (e.g. -1001234567890)")
        except Exception as e:
            await resp.reply(f"❌ Error: <code>{e}</code>\nBot ko channel ka admin banao pehle.")
        return

    # ── Remove FSub ─────────────────────────────────────────────
    if data == "set_removesub":
        fsubs = await get_fsub_channels()
        if not fsubs:
            return await query.answer("❌ Koi FSub channel nahi hai!", show_alert=True)
        await query.answer()
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
        if resp.text.strip() == "/cancel":
            return await resp.delete()
        try:
            ch_id = int(resp.text.strip())
            await remove_fsub(ch_id)
            await resp.reply(f"✅ FSub removed: <code>{ch_id}</code>")
        except ValueError:
            await resp.reply("❌ Valid channel ID bhejo")
        return

    # ── Rename FSub Button ──────────────────────────────────────
    if data == "set_rename_fsub":
        fsubs = await get_fsub_channels()
        if not fsubs:
            return await query.answer("❌ Koi FSub channel nahi hai!", show_alert=True)
        await query.answer()

        lines = []
        for ch_id in fsubs:
            try:
                chat = await client.get_chat(ch_id)
                custom = await get_fsub_channel_name(ch_id)
                current_name = f" (ab: <i>{custom}</i>)" if custom else ""
                lines.append(f"• {chat.title}{current_name}: <code>{ch_id}</code>")
            except Exception:
                lines.append(f"• <code>{ch_id}</code>")

        ask = await query.message.reply(
            "✏️ <b>FSub Button Rename</b>\n\n"
            "Kaun se channel ka button rename karna hai?\n"
            "Niche list se Channel ID copy karke bhejo:\n\n"
            + "\n".join(lines)
            + "\n\n/cancel karo quit karne ke liye."
        )
        try:
            resp_id = await client.listen(
                chat_id=query.from_user.id,
                filters=filters.text,
                timeout=60,
            )
        except asyncio.TimeoutError:
            await ask.delete()
            return
        await ask.delete()
        if resp_id.text.strip() == "/cancel":
            return await resp_id.delete()

        id_text = resp_id.text.strip()
        if not re.match(r"^-100\d+$", id_text):
            return await resp_id.reply("❌ Invalid channel ID. Format: <code>-1001234567890</code>")

        ch_id = int(id_text)
        if ch_id not in fsubs:
            return await resp_id.reply("❌ Yeh channel FSub list mein nahi hai.")

        ask2 = await resp_id.reply(
            "✏️ <b>Ab naya button naam bhejo:</b>\n"
            "Jo bhi text likhoge wahi button pe dikhega.\n\n"
            "<code>remove</code> bhejo custom naam hatane ke liye (wapas channel title).\n"
            "/cancel karo quit karne ke liye."
        )
        try:
            resp_name = await client.listen(
                chat_id=query.from_user.id,
                filters=filters.text,
                timeout=60,
            )
        except asyncio.TimeoutError:
            await ask2.delete()
            return
        await ask2.delete()
        if resp_name.text.strip() == "/cancel":
            return await resp_name.delete()

        new_name = resp_name.text.strip()
        if new_name.lower() == "remove":
            await clear_fsub_channel_name(ch_id)
            return await resp_name.reply(
                f"✅ <b>Custom naam hata diya!</b>\n"
                f"Ab channel ka actual title use hoga.\n"
                f"🆔 <code>{ch_id}</code>"
            )

        if len(new_name) > 50:
            return await resp_name.reply("❌ Naam 50 characters se kam rakho.")

        success = await set_fsub_channel_name(ch_id, new_name)
        if success:
            await resp_name.reply(
                f"✅ <b>Button rename ho gaya!</b>\n\n"
                f"🆔 Channel: <code>{ch_id}</code>\n"
                f"✏️ Button text: <b>{new_name}</b>"
            )
        else:
            await resp_name.reply(
                "❌ Rename failed. Channel pehle add karo:\n"
                "<code>/addsub &lt;channel_id&gt;</code>"
            )
        return

    # ── List FSub ───────────────────────────────────────────────
    if data == "set_listsub":
        await query.answer()
        fsubs = await get_fsub_channels()
        if not fsubs:
            return await query.message.edit_text(
                "📢 <b>Koi FSub channel set nahi hai.</b>",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Back", callback_data="fsub_menu")]]
                ),
            )
        lines = ["<b>📢 Force Sub Channels:</b>\n"]
        for i, ch_id in enumerate(fsubs, 1):
            try:
                chat = await client.get_chat(ch_id)
                link = f"https://t.me/{chat.username}" if chat.username else "—"
                custom = await get_fsub_channel_name(ch_id)
                name_tag = f" [<i>{custom}</i>]" if custom else ""
                lines.append(f"{i}. <b>{chat.title}</b>{name_tag}  🆔 <code>{ch_id}</code>  🔗 {link}")
            except Exception:
                lines.append(f"{i}. <code>{ch_id}</code> (info fetch nahi hua)")
        lines.append(f"\n<b>Total:</b> {len(fsubs)}")
        return await query.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data="fsub_menu")]]
            ),
        )

    # ── Request Mode toggle ─────────────────────────────────────
    if data == "set_reqmode":
        current = await get_fsub_request_mode()
        await set_fsub_request_mode(not current)
        text, markup = await settings_text_and_markup(client)
        await query.message.edit_text(text, reply_markup=markup)
        status = "ON ✅" if not current else "OFF ❌"
        return await query.answer(f"📩 Request Mode: {status}", show_alert=True)

    # ── Fake Link Menu ──────────────────────────────────────────
    if data == "fakelink_menu":
        fake = await get_fake_link()
        status = (
            f"<b>Current:</b> <code>{fake['button_text']}</code> → <code>{fake['url']}</code>"
            if fake else "<i>Koi fake link set nahi hai.</i>"
        )
        await query.message.edit_text(
            f"🔗 <b>Fake Link Settings</b>\n\n{status}",
            reply_markup=await fakelink_menu_markup(),
        )
        return await query.answer()

    # ── Fake Link View ──────────────────────────────────────────
    if data == "set_fakelink_view":
        fake = await get_fake_link()
        if fake:
            return await query.answer(
                f"Text: {fake['button_text']}\nURL: {fake['url']}",
                show_alert=True,
            )
        return await query.answer("❌ Koi fake link set nahi hai!", show_alert=True)

    # ── Fake Link Remove ────────────────────────────────────────
    if data == "set_fakelink_remove":
        result = await remove_fake_link()
        await query.answer(
            "✅ Fake link hata diya!" if result else "❌ Koi fake link set nahi tha.",
            show_alert=True,
        )
        fake = await get_fake_link()
        status = (
            f"<b>Current:</b> <code>{fake['button_text']}</code> → <code>{fake['url']}</code>"
            if fake else "<i>Koi fake link set nahi hai.</i>"
        )
        return await query.message.edit_text(
            f"🔗 <b>Fake Link Settings</b>\n\n{status}",
            reply_markup=await fakelink_menu_markup(),
        )

    # ── Fake Link Set ───────────────────────────────────────────
    if data == "set_fakelink_set":
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
        return

    # ── Set Start Pic ───────────────────────────────────────────
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
        if hasattr(resp, 'text') and resp.text and resp.text.strip() == "/cancel":
            return await resp.delete()
        if hasattr(resp, 'text') and resp.text and resp.text.lower() == "remove":
            await set_setting("start_pic", "")
            await resp.reply("✅ Start pic removed.")
        elif resp.photo:
            await set_setting("start_pic", resp.photo.file_id)
            await resp.reply("✅ Start pic set!")
        elif hasattr(resp, 'text') and resp.text:
            await set_setting("start_pic", resp.text.strip())
            await resp.reply("✅ Start pic URL set!")
        return

    # ── Set Start Message ───────────────────────────────────────
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
        if resp.text.strip() == "/cancel":
            return await resp.delete()
        if resp.text.lower() == "remove":
            await set_setting("start_msg", "")
            await resp.reply("✅ Start message reset to default.")
        else:
            await set_setting("start_msg", resp.text)
            await resp.reply("✅ Start message set!")
        return

    # ════════════════════════════════════════════
    #  ⚡ SHORTENER SECTION
    # ════════════════════════════════════════════

    # ── Shortener Menu ──────────────────────────────────────────
    if data == "shortener_menu":
        s = await get_shortener_settings()
        cfg = await get_bot_config()
        verify_sec = cfg.get("verify_premium_seconds", 86400)
        h = verify_sec // 3600
        m = (verify_sec % 3600) // 60
        dur = f"{h}h" if m == 0 else f"{h}h {m}m"
        api_display = (s["api"][:8] + "...") if s["api"] else "❌ Not set"
        site_display = s["website"] or "❌ Not set"

        await query.message.edit_text(
            f"⚡ <b>Link Shortener Settings</b>\n\n"
            f"📊 Status: <b>{'✅ ON' if s['enabled'] else '❌ OFF'}</b>\n"
            f"🔑 API Key: <code>{api_display}</code>\n"
            f"🌐 Website: <code>{site_display}</code>\n"
            f"⏰ Verify Time: <b>{dur}</b>\n\n"
            f"<i>Free users ko file se pehle ad complete karna padega.\n"
            f"Premium users shortener bypass karte hain.</i>",
            reply_markup=await shortener_menu_markup(),
        )
        return await query.answer()

    # ── Shortener Set API + Site ────────────────────────────────
    if data == "shn_set":
        await query.answer()
        ask = await query.message.reply(
            "⚡ <b>Shortener Set Karo</b>\n\n"
            "Format: <code>API_KEY website.com</code>\n\n"
            "<b>Example:</b>\n"
            "<code>a7ac9b3012c6 omegalinks.in</code>\n"
            "<code>xyz123 urlshortx.com</code>\n\n"
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
        parts = resp.text.strip().split()
        if len(parts) < 2:
            return await resp.reply("❌ Galat format!\nExample: <code>API_KEY website.com</code>")
        api_key = parts[0]
        website = parts[1].lower().replace("https://", "").replace("http://", "").rstrip("/")
        await set_bot_config("shortener_api", api_key)
        await set_bot_config("shortener_website", website)
        await set_bot_config("shortener_enabled", True)
        await resp.reply(
            f"✅ <b>Shortener Set!</b>\n\n"
            f"🔑 API: <code>{api_key[:8]}...</code>\n"
            f"🌐 Site: <code>{website}</code>\n"
            f"📊 Status: <b>ON ✅</b>"
        )
        return

    # ── Shortener Toggle ────────────────────────────────────────
    if data == "shn_toggle_cb":
        s = await get_shortener_settings()
        if not s["api"] and not s["enabled"]:
            return await query.answer("⚠️ Pehle API set karo (🔑 Set API + Site button)!", show_alert=True)
        new = not s["enabled"]
        await set_bot_config("shortener_enabled", new)
        status = "✅ ON" if new else "❌ OFF"
        await query.answer(f"⚡ Shortener: {status}", show_alert=True)
        # Refresh shortener menu
        cfg = await get_bot_config()
        verify_sec = cfg.get("verify_premium_seconds", 86400)
        h = verify_sec // 3600
        m = (verify_sec % 3600) // 60
        dur = f"{h}h" if m == 0 else f"{h}h {m}m"
        s2 = await get_shortener_settings()
        api_display = (s2["api"][:8] + "...") if s2["api"] else "❌ Not set"
        site_display = s2["website"] or "❌ Not set"
        await query.message.edit_text(
            f"⚡ <b>Link Shortener Settings</b>\n\n"
            f"📊 Status: <b>{'✅ ON' if s2['enabled'] else '❌ OFF'}</b>\n"
            f"🔑 API Key: <code>{api_display}</code>\n"
            f"🌐 Website: <code>{site_display}</code>\n"
            f"⏰ Verify Time: <b>{dur}</b>\n\n"
            f"<i>Free users ko file se pehle ad complete karna padega.\n"
            f"Premium users shortener bypass karte hain.</i>",
            reply_markup=await shortener_menu_markup(),
        )
        return

    # ── Shortener Set Verify Time ────────────────────────────────
    if data == "shn_settime":
        await query.answer()
        cfg = await get_bot_config()
        cur = cfg.get("verify_premium_seconds", 86400)
        h = cur // 3600
        m = (cur % 3600) // 60
        ask = await query.message.reply(
            f"⏰ <b>Verify Time Set Karo</b>\n\n"
            f"Current: <b>{h}h {m}m</b>\n\n"
            f"<b>Format:</b> <code>number unit</code>\n\n"
            f"<b>Examples:</b>\n"
            f"<code>6 hour</code>\n"
            f"<code>12 hour</code>\n"
            f"<code>24 hour</code>\n"
            f"<code>1 day</code>\n\n"
            f"<i>Itni der tak user ko shortener dobara complete nahi karna padega.</i>\n\n"
            f"/cancel karo quit karne ke liye."
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
        parts = resp.text.strip().split()
        if len(parts) < 2:
            return await resp.reply("❌ Format: <code>12 hour</code> ya <code>1 day</code>")
        seconds = _parse_time(parts[:2])
        if seconds <= 0:
            return await resp.reply("❌ Invalid! Example: <code>12 hour</code>")
        await set_bot_config("verify_premium_seconds", seconds)
        h2 = seconds // 3600
        m2 = (seconds % 3600) // 60
        await resp.reply(f"✅ Verify time set: <b>{h2}h {m2}m</b>")
        return

    # ── Shortener Remove ─────────────────────────────────────────
    if data == "shn_remove":
        await set_bot_config("shortener_api", "")
        await set_bot_config("shortener_website", "")
        await set_bot_config("shortener_enabled", False)
        await query.answer("🗑 Shortener remove ho gaya!", show_alert=True)
        await query.message.edit_text(
            "⚡ <b>Link Shortener Settings</b>\n\n"
            "📊 Status: <b>❌ OFF</b>\n"
            "🔑 API Key: <code>❌ Not set</code>\n"
            "🌐 Website: <code>❌ Not set</code>\n\n"
            "<i>Shortener remove ho gaya. Pehle API set karo.</i>",
            reply_markup=await shortener_menu_markup(),
        )
        return

    # ════════════════════════════════════════════
    #  📹 TUTORIAL SECTION
    # ════════════════════════════════════════════

    # ── Tutorial Menu ───────────────────────────────────────────
    if data == "tutorial_menu":
        fsub_tut = await get_tutorial_status("fsub")
        shn_tut  = await get_tutorial_status("shortener")
        fsub_info = "✅ Set hai" if fsub_tut["exists"] else "❌ Set nahi"
        shn_info  = "✅ Set hai" if shn_tut["exists"] else "❌ Set nahi"
        fsub_on   = "✅ ON" if fsub_tut["enabled"] else "❌ OFF"
        shn_on    = "✅ ON" if shn_tut["enabled"] else "❌ OFF"
        await query.message.edit_text(
            f"📹 <b>Tutorial Video Settings</b>\n\n"
            f"<b>FSub Tutorial:</b>\n"
            f"  Video: {fsub_info}  |  Status: {fsub_on}\n\n"
            f"<b>Shortener Tutorial:</b>\n"
            f"  Video: {shn_info}  |  Status: {shn_on}\n\n"
            f"<i>30s baad check hoga — user ne join/verify nahi kiya toh auto video bhejega, "
            f"10min baad delete hoga.</i>",
            reply_markup=await tutorial_menu_markup(),
        )
        return await query.answer()

    # ── Set FSub Tutorial Video ─────────────────────────────────
    if data == "tut_set_fsub":
        await query.answer()
        ask = await query.message.reply(
            "<b>📹 FSub Tutorial Video Set Karo</b>\n\n"
            "<blockquote>Woh video bhejo jo FSub join nahi karne wale users ko dikhana hai.\n\n"
            "⏳ 5 minute ka wait hai.</blockquote>\n\n"
            "/cancel karo quit karne ke liye."
        )
        try:
            response = await client.listen(
                chat_id=query.from_user.id,
                filters=filters.video | filters.document | filters.animation | filters.text,
                timeout=300,
            )
        except asyncio.TimeoutError:
            await ask.edit("<b>⏰ Timeout! Dobara try karo.</b>")
            return
        if hasattr(response, 'text') and response.text and response.text.strip() == "/cancel":
            await ask.delete()
            return await response.delete()
        file_id = _extract_file_id(response)
        if not file_id:
            await ask.edit("<b>❌ Sirf video ya document bhejo!</b>")
            return
        try:
            await response.delete()
        except Exception:
            pass
        from database.database import set_tutorial
        success = await set_tutorial("fsub", file_id)
        if success:
            await ask.edit(
                "<b>✅ FSub Tutorial Video Set!</b>\n\n"
                "<blockquote>Jo user 30s mein FSub join nahi karega,\n"
                "usse yeh video jaegi aur 10min baad delete hogi.\n\n"
                "📌 Tutorial ab ON hai.</blockquote>"
            )
        else:
            await ask.edit("<b>❌ Save nahi hua. Dobara try karo.</b>")
        return

    # ── Set Shortener Tutorial Video ────────────────────────────
    if data == "tut_set_shn":
        await query.answer()
        ask = await query.message.reply(
            "<b>📹 Shortener Tutorial Video Set Karo</b>\n\n"
            "<blockquote>Woh video bhejo jo shortener complete nahi karne wale users ko dikhana hai.\n\n"
            "⏳ 5 minute ka wait hai.</blockquote>\n\n"
            "/cancel karo quit karne ke liye."
        )
        try:
            response = await client.listen(
                chat_id=query.from_user.id,
                filters=filters.video | filters.document | filters.animation | filters.text,
                timeout=300,
            )
        except asyncio.TimeoutError:
            await ask.edit("<b>⏰ Timeout! Dobara try karo.</b>")
            return
        if hasattr(response, 'text') and response.text and response.text.strip() == "/cancel":
            await ask.delete()
            return await response.delete()
        file_id = _extract_file_id(response)
        if not file_id:
            await ask.edit("<b>❌ Sirf video ya document bhejo!</b>")
            return
        try:
            await response.delete()
        except Exception:
            pass
        from database.database import set_tutorial
        success = await set_tutorial("shortener", file_id)
        if success:
            await ask.edit(
                "<b>✅ Shortener Tutorial Video Set!</b>\n\n"
                "<blockquote>Jo user shortener complete nahi karega,\n"
                "usse yeh video jaegi aur 10min baad delete hogi.\n\n"
                "📌 Tutorial ab ON hai.</blockquote>"
            )
        else:
            await ask.edit("<b>❌ Save nahi hua. Dobara try karo.</b>")
        return

    # ── Toggle FSub Tutorial ────────────────────────────────────
    if data == "tut_toggle_fsub":
        fsub_tut = await get_tutorial_status("fsub")
        if not fsub_tut["exists"]:
            return await query.answer(
                "❌ Pehle FSub tutorial video set karo!\n(📹 Set FSub Video button)",
                show_alert=True
            )
        new_enabled = not fsub_tut["enabled"]
        ok = await toggle_tutorial("fsub", new_enabled)
        if ok:
            status = "✅ ON" if new_enabled else "❌ OFF"
            await query.answer(f"📹 FSub Tutorial: {status}", show_alert=True)
            # Refresh tutorial menu
            fsub_tut2 = await get_tutorial_status("fsub")
            shn_tut2  = await get_tutorial_status("shortener")
            fsub_info = "✅ Set hai" if fsub_tut2["exists"] else "❌ Set nahi"
            shn_info  = "✅ Set hai" if shn_tut2["exists"] else "❌ Set nahi"
            fsub_on   = "✅ ON" if fsub_tut2["enabled"] else "❌ OFF"
            shn_on    = "✅ ON" if shn_tut2["enabled"] else "❌ OFF"
            await query.message.edit_text(
                f"📹 <b>Tutorial Video Settings</b>\n\n"
                f"<b>FSub Tutorial:</b>\n"
                f"  Video: {fsub_info}  |  Status: {fsub_on}\n\n"
                f"<b>Shortener Tutorial:</b>\n"
                f"  Video: {shn_info}  |  Status: {shn_on}\n\n"
                f"<i>30s baad check hoga — user ne join/verify nahi kiya toh auto video bhejega, "
                f"10min baad delete hoga.</i>",
                reply_markup=await tutorial_menu_markup(),
            )
        else:
            await query.answer("❌ Update nahi hua.", show_alert=True)
        return

    # ── Toggle Shortener Tutorial ───────────────────────────────
    if data == "tut_toggle_shn":
        shn_tut = await get_tutorial_status("shortener")
        if not shn_tut["exists"]:
            return await query.answer(
                "❌ Pehle Shortener tutorial video set karo!\n(📹 Set Shortener Video button)",
                show_alert=True
            )
        new_enabled = not shn_tut["enabled"]
        ok = await toggle_tutorial("shortener", new_enabled)
        if ok:
            status = "✅ ON" if new_enabled else "❌ OFF"
            await query.answer(f"📹 Shortener Tutorial: {status}", show_alert=True)
            # Refresh tutorial menu
            fsub_tut2 = await get_tutorial_status("fsub")
            shn_tut2  = await get_tutorial_status("shortener")
            fsub_info = "✅ Set hai" if fsub_tut2["exists"] else "❌ Set nahi"
            shn_info  = "✅ Set hai" if shn_tut2["exists"] else "❌ Set nahi"
            fsub_on   = "✅ ON" if fsub_tut2["enabled"] else "❌ OFF"
            shn_on    = "✅ ON" if shn_tut2["enabled"] else "❌ OFF"
            await query.message.edit_text(
                f"📹 <b>Tutorial Video Settings</b>\n\n"
                f"<b>FSub Tutorial:</b>\n"
                f"  Video: {fsub_info}  |  Status: {fsub_on}\n\n"
                f"<b>Shortener Tutorial:</b>\n"
                f"  Video: {shn_info}  |  Status: {shn_on}\n\n"
                f"<i>30s baad check hoga — user ne join/verify nahi kiya toh auto video bhejega, "
                f"10min baad delete hoga.</i>",
                reply_markup=await tutorial_menu_markup(),
            )
        else:
            await query.answer("❌ Update nahi hua.", show_alert=True)
        return


# ── Helpers ───────────────────────────────────────────────────────

def _extract_file_id(message) -> str | None:
    """Message se video/document/animation file_id nikalo."""
    if message.video:
        return message.video.file_id
    if message.document:
        return message.document.file_id
    if message.animation:
        return message.animation.file_id
    return None


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
