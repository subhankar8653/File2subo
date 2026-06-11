import base64
import asyncio
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from config import LOGGER

log = LOGGER(__name__)

# ── Encode / Decode ──────────────────────────────────────────────
def encode(string: str) -> str:
    return base64.urlsafe_b64encode(string.encode()).decode().strip("=")

def decode(string: str) -> str:
    string += "=" * (-len(string) % 4)
    return base64.urlsafe_b64decode(string.encode()).decode()

# ── Make deep link ───────────────────────────────────────────────
async def make_link(bot: Client, msg_id: int) -> str:
    me = await bot.get_me()
    encoded = encode(f"get-{msg_id}")
    return f"https://t.me/{me.username}?start={encoded}"

async def make_batch_link(bot: Client, first_id: int, last_id: int) -> str:
    me = await bot.get_me()
    encoded = encode(f"batch-{first_id}-{last_id}")
    return f"https://t.me/{me.username}?start={encoded}"

# ── Get message id from forwarded msg or t.me link ───────────────
async def get_msg_id(client: Client, message: Message, log_channel: int):
    """Extract msg ID from a forwarded message or channel link, or forward to log channel."""

    # 1. Forwarded from log channel
    origin = getattr(message, "forward_origin", None)
    if origin:
        chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
        if chat and chat.id == log_channel:
            return getattr(origin, "message_id", None)

    # Old pyrogram style
    ffc = getattr(message, "forward_from_chat", None)
    if ffc and ffc.id == log_channel:
        return getattr(message, "forward_from_message_id", None)

    # 2. t.me link
    if message.text:
        import re
        m = re.search(r"https?://t\.me/(?:c/)?([^/]+)/(\d+)", message.text)
        if m:
            chat_part, msg_id = m.group(1), int(m.group(2))
            if chat_part.isdigit() and int(f"-100{chat_part}") == log_channel:
                return msg_id
            try:
                chat = await client.get_chat(log_channel)
                if chat.username and chat.username.lower() == chat_part.lower():
                    return msg_id
            except Exception:
                pass

    # 3. Forward to log channel and store
    if message.service:
        return None
    try:
        fwd = await message.forward(log_channel)
        return fwd.id
    except Exception as e:
        log.error(f"Forward error: {e}")
        return None

# ── Fetch messages from channel ───────────────────────────────────
async def get_messages(client: Client, channel_id: int, ids: list) -> list:
    msgs = []
    for i in range(0, len(ids), 200):
        batch = ids[i:i+200]
        try:
            result = await client.get_messages(channel_id, batch)
            if isinstance(result, list):
                msgs.extend(result)
            else:
                msgs.append(result)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            result = await client.get_messages(channel_id, batch)
            if isinstance(result, list):
                msgs.extend(result)
            else:
                msgs.append(result)
        except Exception as e:
            log.error(f"get_messages error: {e}")
    return msgs

# ── Readable file size ───────────────────────────────────────────
def readable_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
