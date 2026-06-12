import base64
import re
import asyncio
import logging
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, FloodWait
from config import ADMINS, AUTO_DELETE_TIME, AUTO_DEL_SUCCESS_MSG

log = logging.getLogger(__name__)

# ── Encode / Decode ───────────────────────────────────────────────

async def encode(string: str) -> str:
    b = base64.urlsafe_b64encode(string.encode("ascii"))
    return b.decode("ascii").strip("=")

async def decode(string: str) -> str:
    string = string.strip("=")
    b = (string + "=" * (-len(string) % 4)).encode("ascii")
    return base64.urlsafe_b64decode(b).decode("ascii")

# ── Force Sub filter ──────────────────────────────────────────────

async def is_subscribed(filter, client, update):
    from database.database import get_fsub_channels, get_fsub_request_mode, has_fsub_request
    user_id = update.from_user.id
    if user_id in ADMINS:
        return True
    fsubs = await get_fsub_channels()
    if not fsubs:
        return True

    req_mode = await get_fsub_request_mode()

    for ch_id in fsubs:
        try:
            member = await client.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status not in [
                ChatMemberStatus.OWNER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.MEMBER,
            ]:
                return False
        except UserNotParticipant:
            # Request mode ON hai — check karo ki user ne request bheja hai
            if req_mode and await has_fsub_request(ch_id, user_id):
                continue  # Request pending hai — OK maano
            return False
        except Exception:
            pass
    return True

subscribed = filters.create(is_subscribed)

# ── Get messages from DB channel ──────────────────────────────────

async def get_messages(client, message_ids: list) -> list:
    messages = []
    total = 0
    while total != len(message_ids):
        batch = message_ids[total:total + 200]
        try:
            msgs = await client.get_messages(
                chat_id=client.db_channel.id,
                message_ids=batch
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            msgs = await client.get_messages(
                chat_id=client.db_channel.id,
                message_ids=batch
            )
        except Exception as e:
            log.error(f"get_messages error: {e}")
            break
        total += len(batch)
        messages.extend(msgs if isinstance(msgs, list) else [msgs])
    return messages

# ── Get message ID from forwarded msg or t.me link ────────────────

async def get_message_id(client, message) -> int:
    if message.forward_from_chat:
        if message.forward_from_chat.id == client.db_channel.id:
            return message.forward_from_message_id
        return 0
    elif getattr(message, "forward_sender_name", None):
        return 0
    elif message.text:
        pattern = r"https://t\.me/(?:c/)?(.*)/(\\d+)"
        matches = re.match(r"https://t\.me/(?:c/)?([^/]+)/(\d+)", message.text)
        if not matches:
            return 0
        channel_id = matches.group(1)
        msg_id = int(matches.group(2))
        if channel_id.isdigit():
            if f"-100{channel_id}" == str(client.db_channel.id):
                return msg_id
        else:
            if channel_id == getattr(client.db_channel, "username", None):
                return msg_id
    return 0

# ── Auto delete ───────────────────────────────────────────────────

async def delete_file(messages, client, process, delay: int = None):
    if delay is None:
        delay = AUTO_DELETE_TIME
    await asyncio.sleep(delay)
    for msg in messages:
        try:
            await client.delete_messages(chat_id=msg.chat.id, message_ids=[msg.id])
        except Exception as e:
            log.error(f"Auto-delete error for msg {msg.id}: {e}")
    try:
        await process.edit_text(AUTO_DEL_SUCCESS_MSG)
    except Exception:
        pass

# ── Readable time ─────────────────────────────────────────────────

def get_readable_time(seconds: int) -> str:
    count = 0
    up_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        up_time += f"{time_list.pop()}, "
    time_list.reverse()
    up_time += ":".join(time_list)
    return up_time
