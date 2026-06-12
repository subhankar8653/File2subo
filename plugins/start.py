import asyncio
import secrets
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from bot import Bot
from config import (
    ADMINS, FORCE_MSG, START_MSG, START_PIC,
    CUSTOM_CAPTION, DISABLE_CHANNEL_BUTTON, PROTECT_CONTENT,
    AUTO_DELETE_TIME, AUTO_DELETE_MSG, JOIN_REQUEST_ENABLE, FORCE_SUB_CHANNEL
)
from helper_func import subscribed, decode, get_messages, delete_file
from database.database import (
    add_user, del_user, full_userbase, present_user,
    get_setting,
    get_fsub_channels, get_fsub_request_mode,
    add_fsub_request, remove_fsub_request, has_fsub_request,
    get_fake_link, get_fsub_channel_name,
    get_shortener_settings, get_bot_config,
    has_premium_access,
    create_verify_token, get_verify_token, mark_token_used,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ChatJoinRequest handler — Request Mode
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_chat_join_request()
async def on_join_request(client: Client, request: ChatJoinRequest):
    try:
        req_mode = await get_fsub_request_mode()
        if not req_mode:
            return
        fsubs = await get_fsub_channels()
        ch_id = request.chat.id
        uid   = request.from_user.id
        if ch_id not in fsubs:
            return
        await add_fsub_request(ch_id, uid)
    except Exception as e:
        import logging; logging.getLogger(__name__).error(f"on_join_request error: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Shortener verify handler
#  User /start vfy_<token> ke saath aata hai
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _handle_verify_token(client: Client, message: Message, uid: int, token: str):
    doc = await get_verify_token(token)

    if not doc:
        return await message.reply(
            "<b>⚠️ Invalid ya expired verification link.</b>\n\n"
            "<i>Dobara try karo — original file link pe click karo.</i>"
        )

    if doc.get("used"):
        return await message.reply(
            "<b>⚠️ Yeh link pehle use ho chuka hai.</b>\n\n"
            "<i>Dobara file link pe click karo.</i>"
        )

    if doc.get("user_id") and doc["user_id"] != uid:
        return await message.reply("<b>⚠️ Yeh link tumhare liye nahi hai.</b>")

    # Token valid — temp premium do
    cfg     = await get_bot_config()
    seconds = cfg.get("verify_premium_seconds", 86400)  # default 24h

    from database.database import add_premium, get_premium_expiry
    await add_premium(uid, seconds)

    # Token use mark karo
    await mark_token_used(token)

    h = seconds // 3600
    m = (seconds % 3600) // 60
    dur = f"{h}h" if m == 0 else f"{h}h {m}m"

    # User ko original deep link dobara bhejo
    original_param = doc.get("original_param", "")
    if original_param:
        bot_link = f"https://t.me/{client.username}?start={original_param}"
        await message.reply(
            f"✅ <b>Verified!</b>\n\n"
            f"<blockquote>"
            f"⚡ Agle <b>{dur}</b> tak direct links milenge — koi shortener nahi!\n"
            f"Time khatam hone ke baad dobara ad complete karna padega."
            f"</blockquote>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📂 File Lo", url=bot_link)
            ]])
        )
    else:
        await message.reply(
            f"✅ <b>Verified!</b>\n\n"
            f"<blockquote>"
            f"⚡ Agle <b>{dur}</b> tak direct links milenge!\n"
            f"Ab original file link dobara click karo."
            f"</blockquote>"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /start — subscribed users
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_message(filters.command("start") & filters.private & subscribed)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    if not await present_user(user_id):
        await add_user(user_id)

    text = message.text

    # ── Verify token (shortener ad complete ke baad) ───────────────
    if len(text) > 7:
        param = text.split(" ", 1)[1]

        if param.startswith("vfy_"):
            return await _handle_verify_token(client, message, user_id, param[4:])

        # ── Normal deep link — file delivery ──────────────────────
        try:
            base64_string = param
        except Exception:
            return

        string   = await decode(base64_string)
        argument = string.split("-")

        if len(argument) == 3:
            try:
                start = int(int(argument[1]) / abs(client.db_channel.id))
                end   = int(int(argument[2]) / abs(client.db_channel.id))
            except Exception:
                return
            ids = list(range(start, end + 1)) if start <= end else list(range(start, end - 1, -1))
        elif len(argument) == 2:
            try:
                ids = [int(int(argument[1]) / abs(client.db_channel.id))]
            except Exception:
                return
        else:
            return

        # ── Shortener check ────────────────────────────────────────
        # Agar shortener ON hai aur user premium nahi — pehle ad dikhao
        s = await get_shortener_settings()
        if s["enabled"] and s["api"] and not await has_premium_access(user_id):
            # Token banao
            token    = secrets.token_urlsafe(12)
            await create_verify_token(user_id, token)

            # original_param save karo — verify ke baad yahi use hoga
            from database.database import verify_tokens_col
            await verify_tokens_col.update_one(
                {"token": token},
                {"$set": {"original_param": base64_string}}
            )

            from plugins.shortener import shorten_link
            bot_link  = f"https://t.me/{client.username}?start=vfy_{token}"
            short_url = await shorten_link(bot_link)

            await message.reply(
                "<b>🔗 File milne se pehle ek step complete karo!</b>\n\n"
                "<blockquote>"
                "Niche button dabao, ek short ad complete karo.\n"
                "Uske baad automatically file mil jaegi — <b>koi waiting nahi!</b>\n\n"
                "⚡ <b>Pehle se verified ho?</b> Toh seedha file milegi."
                "</blockquote>",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔗 Get File", url=short_url)
                ]])
            )

            # Shortener tutorial — 30s baad check
            from plugins.tutorial import send_shortener_tutorial_if_not_verified
            asyncio.create_task(
                send_shortener_tutorial_if_not_verified(client, user_id, token)
            )
            return

        # ── Direct file delivery ───────────────────────────────────
        temp_msg = await message.reply("⏳ <b>Please wait...</b>")
        try:
            messages = await get_messages(client, ids)
        except Exception:
            await message.reply("❌ Something went wrong. Try again.")
            return
        await temp_msg.delete()

        protect  = await get_setting("protect_content", PROTECT_CONTENT)
        auto_del = await get_setting("auto_delete_time", AUTO_DELETE_TIME)
        track_msgs = []

        for msg in messages:
            if bool(CUSTOM_CAPTION) and bool(msg.document):
                caption = CUSTOM_CAPTION.format(
                    previouscaption="" if not msg.caption else msg.caption.html,
                    filename=msg.document.file_name
                )
            else:
                caption = "" if not msg.caption else msg.caption.html

            reply_markup = msg.reply_markup if DISABLE_CHANNEL_BUTTON else None

            try:
                copied = await msg.copy(
                    chat_id=user_id,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    protect_content=protect,
                )
                if auto_del and auto_del > 0 and copied:
                    track_msgs.append(copied)
                await asyncio.sleep(0.5)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                copied = await msg.copy(
                    chat_id=user_id,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    protect_content=protect,
                )
                if auto_del and auto_del > 0 and copied:
                    track_msgs.append(copied)
            except Exception as e:
                print(f"Copy error: {e}")

        if track_msgs:
            if auto_del >= 60:
                mins = auto_del // 60
                secs = auto_del % 60
                time_str = f"{mins} minute{'s' if mins > 1 else ''}" + (f" {secs} seconds" if secs else "")
            else:
                time_str = f"{auto_del} seconds"
            delete_data = await client.send_message(
                chat_id=user_id,
                text=AUTO_DELETE_MSG.format(time=time_str)
            )
            asyncio.create_task(delete_file(track_msgs, client, delete_data, auto_del))

        return

    # Normal /start
    db_start_pic = await get_setting("start_pic", "") or START_PIC
    db_start_msg = await get_setting("start_msg", "") or START_MSG

    reply_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("😊 About Me", callback_data="about"),
        InlineKeyboardButton("🔒 Close", callback_data="close"),
    ]])

    fmt = dict(
        first=message.from_user.first_name,
        last=message.from_user.last_name or "",
        username=None if not message.from_user.username else "@" + message.from_user.username,
        mention=message.from_user.mention,
        id=message.from_user.id,
    )

    if db_start_pic:
        await message.reply_photo(
            photo=db_start_pic,
            caption=db_start_msg.format(**fmt),
            reply_markup=reply_markup,
            quote=True,
        )
    else:
        await message.reply_text(
            text=db_start_msg.format(**fmt),
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            quote=True,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /start — NOT subscribed
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_message(filters.command("start") & filters.private)
async def not_joined(client: Client, message: Message):
    fsubs = await get_fsub_channels()

    if not fsubs:
        return await start_command(client, message)

    req_mode = await get_fsub_request_mode()
    buttons  = []

    fake = await get_fake_link()
    if fake:
        buttons.append([InlineKeyboardButton(fake["button_text"], url=fake["url"])])

    for ch_id in fsubs:
        try:
            if req_mode:
                invite = await client.create_chat_invite_link(
                    chat_id=ch_id, creates_join_request=True
                )
                url = invite.invite_link
            else:
                chat = await client.get_chat(ch_id)
                url  = chat.invite_link or await client.export_chat_invite_link(ch_id)
            chat = await client.get_chat(ch_id)
            custom_name = await get_fsub_channel_name(ch_id)
            btn_text = custom_name if custom_name else f"📢 {chat.title}"
            buttons.append([InlineKeyboardButton(btn_text, url=url)])
        except Exception:
            pass

    try:
        buttons.append([InlineKeyboardButton(
            "🔄 Try Again",
            url=f"https://t.me/{client.username}?start={message.command[1]}"
        )])
    except IndexError:
        buttons.append([InlineKeyboardButton(
            "🔄 Try Again",
            url=f"https://t.me/{client.username}?start=start"
        )])

    await message.reply(
        text=FORCE_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name or "",
            username=None if not message.from_user.username else "@" + message.from_user.username,
            mention=message.from_user.mention,
            id=message.from_user.id,
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True,
        disable_web_page_preview=True,
    )

    # FSub tutorial — 30s baad check
    uid = message.from_user.id
    async def _check_joined_all(check_uid: int) -> bool:
        try:
            from pyrogram.enums import ChatMemberStatus
            from pyrogram.errors import UserNotParticipant
            chs = await get_fsub_channels()
            for cid in chs:
                try:
                    m = await client.get_chat_member(cid, check_uid)
                    if m.status not in {
                        ChatMemberStatus.OWNER,
                        ChatMemberStatus.ADMINISTRATOR,
                        ChatMemberStatus.MEMBER,
                    }:
                        return False
                except Exception:
                    if req_mode and await has_fsub_request(cid, check_uid):
                        continue
                    return False
            return True
        except Exception:
            return False

    from plugins.tutorial import send_fsub_tutorial_if_not_joined
    asyncio.create_task(send_fsub_tutorial_if_not_joined(client, uid, _check_joined_all))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /users  /broadcast
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_message(filters.command("users") & filters.private & filters.user(ADMINS))
async def get_users(client: Bot, message: Message):
    msg = await message.reply("⏳ Counting...")
    users = await full_userbase()
    await msg.edit(f"👥 <b>{len(users)}</b> users are using this bot.")


@Bot.on_message(filters.command("broadcast") & filters.private & filters.user(ADMINS))
async def send_broadcast(client: Bot, message: Message):
    if not message.reply_to_message:
        return await message.reply("↩️ Reply to a message to broadcast it.")

    query         = await full_userbase()
    broadcast_msg = message.reply_to_message
    total = successful = blocked = deleted = unsuccessful = 0

    pls_wait = await message.reply("<i>📣 Broadcasting... this will take some time.</i>")
    for chat_id in query:
        try:
            await broadcast_msg.copy(chat_id)
            successful += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await broadcast_msg.copy(chat_id)
            successful += 1
        except UserIsBlocked:
            await del_user(chat_id)
            blocked += 1
        except InputUserDeactivated:
            await del_user(chat_id)
            deleted += 1
        except Exception:
            unsuccessful += 1
        total += 1

    await pls_wait.edit(
        f"<b><u>✅ Broadcast Done</u>\n\n"
        f"Total: <code>{total}</code>\n"
        f"Success: <code>{successful}</code>\n"
        f"Blocked: <code>{blocked}</code>\n"
        f"Deleted: <code>{deleted}</code>\n"
        f"Failed: <code>{unsuccessful}</code></b>"
    )
