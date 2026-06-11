import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
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

    # Deep link — file delivery
    if len(text) > 7:
        try:
            base64_string = text.split(" ", 1)[1]
        except Exception:
            return

        string = await decode(base64_string)
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

        temp_msg = await message.reply("⏳ <b>Please wait...</b>")
        try:
            messages = await get_messages(client, ids)
        except Exception:
            await message.reply("❌ Something went wrong. Try again.")
            return
        await temp_msg.delete()

        # Read settings from DB (override config defaults)
        protect   = await get_setting("protect_content", PROTECT_CONTENT)
        auto_del  = await get_setting("auto_delete_time", AUTO_DELETE_TIME)

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
            delete_data = await client.send_message(
                chat_id=user_id,
                text=AUTO_DELETE_MSG.format(time=auto_del)
            )
            asyncio.create_task(delete_file(track_msgs, client, delete_data, auto_del))

        return

    # Normal /start — read start_pic and start_msg from DB
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
    # Get active fsub channels from DB
    from database.database import get_fsub_channels, get_fake_link, get_fsub_request_mode
    fsubs = await get_fsub_channels()

    if not fsubs:
        # No fsub set — treat as subscribed, re-route to start_command
        return await start_command(client, message)

    req_mode = await get_fsub_request_mode()
    buttons = []

    # Fake link button — sabse pehle dikhao (same as link-sharing-bot logic)
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
                url = chat.invite_link or await client.export_chat_invite_link(ch_id)
            chat = await client.get_chat(ch_id)
            buttons.append([InlineKeyboardButton(f"📢 {chat.title}", url=url)])
        except Exception:
            pass

    try:
        buttons.append([
            InlineKeyboardButton(
                "🔄 Try Again",
                url=f"https://t.me/{client.username}?start={message.command[1]}"
            )
        ])
    except IndexError:
        pass

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

    query = await full_userbase()
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
