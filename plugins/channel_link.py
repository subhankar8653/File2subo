"""
plugins/channel_link.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
File-to-Link Channel System

Admin Commands (DM only):
  /setftlchannel   — File-to-Link channel set karo
  /removeftlchannel — channel hata do
  /ftlstatus       — current status dekho

Channel Commands (FTL channel mein):
  /batch           — batch mode shuru karo
  /complete        — batch khatam karo, sorted link bhejo

Auto Mode:
  Koi bhi file post karo FTL channel pe → instant link milega
  (Batch mode ON ho tab file batch mein jama hogi, link nahi aayega)

Smart Sorting Logic:
  - Episode number detect karta hai (E01, Ep01, Episode 1, S01E01, etc.)
  - Quality detect karta hai (360p, 480p, 720p, 1080p, 4K, etc.)
  - Pehle episode number se sort, phir quality se (360 → 480 → 720 → 1080 → 4K)
  - Agar episode same ho toh quality ke order mein dega
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import re
import asyncio
import logging

from pyrogram import filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton
)
from pyrogram.errors import FloodWait

from bot import Bot
from config import ADMINS
from helper_func import encode
from database.database import (
    get_ftl_channel, set_ftl_channel, remove_ftl_channel,
    ftl_batch_start, ftl_batch_add, ftl_batch_get,
    ftl_batch_exists, ftl_batch_clear,
)

log = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SMART SORT HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Quality order — low to high
QUALITY_ORDER = {
    "144": 1, "240": 2, "360": 3, "480": 4,
    "540": 5, "720": 6, "1080": 7, "2160": 8, "4k": 8, "4K": 8,
}

# Regex patterns for episode detection
# Covers: S01E01, E01, Ep01, Episode 1, EP 01, Part 1, etc.
_EP_PATTERNS = [
    r"[Ss]\d{1,3}[Ee](\d{1,3})",          # S01E05
    r"[Ee][Pp]?(?:isode)?\s*(\d{1,3})",   # E05, Ep05, Episode 5, EP 05
    r"[Pp]art\s*(\d{1,3})",               # Part 3
    r"(?<!\d)(\d{1,3})(?!\d)",            # bare number fallback
]

_QUALITY_PATTERN = re.compile(
    r"(\d{3,4})[Pp]|([Ff]ull\s*[Hh][Dd])|([Hh][Dd])|([Ss][Dd])|(4[Kk])"
)


def _extract_episode(name: str) -> int:
    """File name se episode number nikalo. 0 = nahi mila."""
    for pat in _EP_PATTERNS[:-1]:   # bare number last
        m = re.search(pat, name, re.IGNORECASE)
        if m:
            return int(m.group(1))
    # bare number — only if no other pattern matched
    m = re.search(_EP_PATTERNS[-1], name)
    if m:
        return int(m.group(1))
    return 0


def _extract_quality(name: str) -> int:
    """File name se quality nikalo as sort key. 0 = unknown (last mein)."""
    m = _QUALITY_PATTERN.search(name)
    if not m:
        return 0
    if m.group(1):                      # 360p, 720p, 1080p, etc.
        return QUALITY_ORDER.get(m.group(1), 0)
    if m.group(5):                      # 4K
        return QUALITY_ORDER["4k"]
    if m.group(2) or m.group(3):        # Full HD, HD
        return QUALITY_ORDER.get("1080", 7)
    if m.group(4):                      # SD
        return QUALITY_ORDER.get("480", 4)
    return 0


def _smart_sort(files: list) -> list:
    """
    files = [{"msg_id": int, "name": str}, ...]
    Returns same list sorted by (episode, quality).
    """
    def sort_key(f):
        name = f.get("name", "")
        ep   = _extract_episode(name)
        qual = _extract_quality(name)
        return (ep, qual)

    return sorted(files, key=sort_key)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LINK BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _make_single_link(client, msg_id: int) -> str:
    converted = msg_id * abs(client.db_channel.id)
    b64 = await encode(f"get-{converted}")
    return f"https://t.me/{client.username}?start={b64}"


async def _make_batch_link(client, first_id: int, last_id: int) -> str:
    string = f"get-{first_id * abs(client.db_channel.id)}-{last_id * abs(client.db_channel.id)}"
    b64 = await encode(string)
    return f"https://t.me/{client.username}?start={b64}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADMIN COMMANDS (DM)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@Bot.on_message(
    filters.command("setftlchannel") & filters.private & filters.user(ADMINS)
)
async def cmd_set_ftl_channel(client: Bot, message: Message):
    """
    /setftlchannel — File-to-Link channel set karo
    Bot ko us channel ka admin hona chahiye.
    """
    ask = await message.reply(
        "📢 <b>File-to-Link Channel Set Karo</b>\n\n"
        "Channel ID bhejo (e.g. <code>-1001234567890</code>)\n"
        "Bot ko us channel ka admin hona chahiye.\n\n"
        "/cancel karo quit karne ke liye."
    )
    try:
        resp = await client.listen(
            chat_id=message.from_user.id,
            filters=filters.text,
            timeout=60,
        )
    except asyncio.TimeoutError:
        await ask.delete()
        return
    if resp.text.strip() == "/cancel":
        await ask.delete()
        return await resp.delete()

    try:
        ch_id = int(resp.text.strip())
    except ValueError:
        return await resp.reply("❌ Valid channel ID bhejo (e.g. <code>-1001234567890</code>)")

    # Verify bot is admin
    try:
        chat = await client.get_chat(ch_id)
        me   = await client.get_chat_member(ch_id, (await client.get_me()).id)
        from pyrogram.enums import ChatMemberStatus
        if me.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return await resp.reply(
                f"❌ Bot <b>{chat.title}</b> ka admin nahi hai!\n"
                "Pehle admin banao, fir dobara try karo."
            )
    except Exception as e:
        return await resp.reply(
            f"❌ Channel verify nahi hua: <code>{e}</code>\n"
            "Bot ko channel ka admin banana padega."
        )

    await set_ftl_channel(ch_id)
    await resp.reply(
        f"✅ <b>File-to-Link Channel Set!</b>\n\n"
        f"📢 Channel: <b>{chat.title}</b>\n"
        f"🆔 ID: <code>{ch_id}</code>\n\n"
        f"<b>Ab yeh channel pe:</b>\n"
        f"• Koi bhi file bhejo → instant link milega\n"
        f"• <code>/batch</code> → batch mode ON\n"
        f"• <code>/complete</code> → sorted batch link\n\n"
        f"<i>Smart sorting: episode order + quality order (360p→720p→1080p)</i>"
    )


@Bot.on_message(
    filters.command("removeftlchannel") & filters.private & filters.user(ADMINS)
)
async def cmd_remove_ftl_channel(client: Bot, message: Message):
    ch_id = await get_ftl_channel()
    if not ch_id:
        return await message.reply("❌ Koi FTL channel set nahi hai.")
    await remove_ftl_channel()
    await message.reply("🗑 <b>File-to-Link channel hata diya!</b>")


@Bot.on_message(
    filters.command("ftlstatus") & filters.private & filters.user(ADMINS)
)
async def cmd_ftl_status(client: Bot, message: Message):
    ch_id = await get_ftl_channel()
    if not ch_id:
        return await message.reply(
            "⚙️ <b>File-to-Link Status</b>\n\n"
            "❌ Koi channel set nahi hai.\n\n"
            "Set karne ke liye: <code>/setftlchannel</code>"
        )
    try:
        chat = await client.get_chat(ch_id)
        name = chat.title
    except Exception:
        name = "—"

    batch_active = await ftl_batch_exists(ch_id)
    batch_count  = len(await ftl_batch_get(ch_id)) if batch_active else 0

    await message.reply(
        f"⚙️ <b>File-to-Link Status</b>\n\n"
        f"📢 Channel: <b>{name}</b>\n"
        f"🆔 ID: <code>{ch_id}</code>\n"
        f"📦 Batch Mode: {'✅ Active (' + str(batch_count) + ' files)' if batch_active else '❌ Off'}\n\n"
        f"<b>Channel Commands:</b>\n"
        f"<code>/batch</code> — batch mode shuru karo\n"
        f"<code>/complete</code> — batch khatam karo\n\n"
        f"<b>DM Commands:</b>\n"
        f"<code>/setftlchannel</code>\n"
        f"<code>/removeftlchannel</code>"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CHANNEL COMMANDS: /batch  /complete
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _is_ftl_channel(client, chat_id: int) -> bool:
    ftl = await get_ftl_channel()
    return ftl is not None and ftl == chat_id


@Bot.on_message(
    filters.command("batch") & filters.channel
)
async def cmd_channel_batch(client: Bot, message: Message):
    if not await _is_ftl_channel(client, message.chat.id):
        return

    ch_id = message.chat.id
    try:
        await message.delete()
    except Exception:
        pass

    if await ftl_batch_exists(ch_id):
        count = len(await ftl_batch_get(ch_id))
        notice = await client.send_message(
            ch_id,
            f"⚠️ <b>Batch already active!</b> ({count} files)\n"
            f"<code>/complete</code> bhejo finish karne ke liye.\n"
            f"<i>(Yeh message 10s mein delete hoga)</i>"
        )
        await asyncio.sleep(10)
        try:
            await notice.delete()
        except Exception:
            pass
        return

    await ftl_batch_start(ch_id)
    notice = await client.send_message(
        ch_id,
        "📦 <b>Batch Mode ON!</b>\n\n"
        "Ab files bhejo — sab collect hogi.\n"
        "Jab done ho toh <code>/complete</code> bhejo.\n\n"
        "<i>Smart sort hogi: Episode order + Quality order (360p→720p→1080p)</i>\n"
        "<i>(Yeh message 15s mein delete hoga)</i>"
    )
    await asyncio.sleep(15)
    try:
        await notice.delete()
    except Exception:
        pass


@Bot.on_message(
    filters.command("complete") & filters.channel
)
async def cmd_channel_complete(client: Bot, message: Message):
    if not await _is_ftl_channel(client, message.chat.id):
        return

    ch_id = message.chat.id
    try:
        await message.delete()
    except Exception:
        pass

    if not await ftl_batch_exists(ch_id):
        notice = await client.send_message(
            ch_id,
            "❌ <b>Koi active batch nahi hai!</b>\n"
            "Pehle <code>/batch</code> bhejo.\n"
            "<i>(Yeh message 10s mein delete hoga)</i>"
        )
        await asyncio.sleep(10)
        try:
            await notice.delete()
        except Exception:
            pass
        return

    files = await ftl_batch_get(ch_id)

    if not files:
        await ftl_batch_clear(ch_id)
        notice = await client.send_message(
            ch_id,
            "⚠️ <b>Batch mein koi file nahi thi!</b>\n"
            "<i>(Yeh message 10s mein delete hoga)</i>"
        )
        await asyncio.sleep(10)
        try:
            await notice.delete()
        except Exception:
            pass
        return

    # ── Smart Sort ──────────────────────────────────────────────
    sorted_files = _smart_sort(files)

    # ── Generate link ───────────────────────────────────────────
    # Batch link: first_id → last_id (sorted order)
    # NOTE: Batch link uses consecutive msg_id range.
    # Agar files non-consecutive hain toh har file ka individual link dega
    # aur ek combined batch link bhi dega (start to end range).

    count = len(sorted_files)
    first_id = sorted_files[0]["msg_id"]
    last_id  = sorted_files[-1]["msg_id"]

    # Check if IDs are consecutive (or need individual links)
    ids = [f["msg_id"] for f in sorted_files]
    # Sort IDs for range check
    ids_sorted_num = sorted(ids)
    is_consecutive = (ids_sorted_num[-1] - ids_sorted_num[0] + 1 == len(ids_sorted_num))

    if count == 1:
        link = await _make_single_link(client, first_id)
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔁 Share", url=f"https://telegram.me/share/url?url={link}")
        ]])
        result_msg = (
            f"✅ <b>File Link:</b>\n\n"
            f"📄 {sorted_files[0]['name']}\n\n"
            f"<code>{link}</code>"
        )
    elif is_consecutive:
        # Real batch link — most efficient
        # Use the sorted order's first/last for display but original min/max for link
        min_id = ids_sorted_num[0]
        max_id = ids_sorted_num[-1]
        link   = await _make_batch_link(client, min_id, max_id)
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔁 Share", url=f"https://telegram.me/share/url?url={link}")
        ]])
        # Build sorted file list display
        file_list = "\n".join(
            f"{i+1}. {f['name']}" for i, f in enumerate(sorted_files)
        )
        result_msg = (
            f"✅ <b>Batch Link — {count} Files</b>\n\n"
            f"<b>Sorted Order:</b>\n"
            f"<blockquote>{file_list}</blockquote>\n\n"
            f"<code>{link}</code>"
        )
    else:
        # Non-consecutive — individual links for each file (sorted order)
        lines = []
        for i, f in enumerate(sorted_files):
            l = await _make_single_link(client, f["msg_id"])
            lines.append(f"{i+1}. {f['name']}\n<code>{l}</code>")

        # Also a combined link (min→max range, may include gaps)
        combined = await _make_batch_link(client, ids_sorted_num[0], ids_sorted_num[-1])
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔗 Combined Link", url=f"https://telegram.me/share/url?url={combined}")
        ]])
        file_list_text = "\n\n".join(lines)
        result_msg = (
            f"✅ <b>Batch Done — {count} Files</b>\n\n"
            f"<b>Sorted Links:</b>\n\n"
            f"{file_list_text}\n\n"
            f"<b>Combined Link:</b>\n<code>{combined}</code>"
        )

    await ftl_batch_clear(ch_id)
    await client.send_message(
        ch_id,
        result_msg,
        reply_markup=markup,
        disable_web_page_preview=True,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AUTO LINK — any file posted in FTL channel
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# File types we handle
_FILE_FILTER = (
    filters.document | filters.video | filters.audio |
    filters.photo | filters.animation
)


@Bot.on_message(filters.channel & _FILE_FILTER)
async def ftl_auto_link(client: Bot, message: Message):
    """
    FTL channel mein koi file aaya:
    - Batch mode ON → file collect karo, link mat do
    - Batch mode OFF → seedha DB channel pe copy karo + link do
    """
    ftl = await get_ftl_channel()
    if not ftl or ftl != message.chat.id:
        return  # Not our FTL channel

    file_name = _get_file_name(message)
    ch_id     = message.chat.id

    # ── Batch mode active? ───────────────────────────────────────
    if await ftl_batch_exists(ch_id):
        # Copy to DB channel
        try:
            db_msg = await message.copy(
                chat_id=client.db_channel.id,
                disable_notification=True,
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            db_msg = await message.copy(
                chat_id=client.db_channel.id,
                disable_notification=True,
            )
        except Exception as e:
            log.error(f"ftl_auto_link copy error (batch): {e}")
            return

        await ftl_batch_add(ch_id, db_msg.id, file_name)

        # Small ack (auto-delete in 5s)
        ack = await client.send_message(
            ch_id,
            f"📥 <b>Added to batch:</b> {file_name}\n"
            f"<i>(Yeh message 5s mein delete hoga)</i>"
        )
        await asyncio.sleep(5)
        try:
            await ack.delete()
        except Exception:
            pass
        return

    # ── Single file → instant link ───────────────────────────────
    try:
        db_msg = await message.copy(
            chat_id=client.db_channel.id,
            disable_notification=True,
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
        db_msg = await message.copy(
            chat_id=client.db_channel.id,
            disable_notification=True,
        )
    except Exception as e:
        log.error(f"ftl_auto_link copy error (single): {e}")
        return

    link   = await _make_single_link(client, db_msg.id)
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔁 Share", url=f"https://telegram.me/share/url?url={link}")
    ]])

    await client.send_message(
        ch_id,
        f"✅ <b>Link Ready!</b>\n\n"
        f"📄 <b>{file_name}</b>\n\n"
        f"<code>{link}</code>",
        reply_markup=markup,
        disable_web_page_preview=True,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_file_name(message: Message) -> str:
    """Message se file name nikalo."""
    if message.document:
        return message.document.file_name or "document"
    if message.video:
        return message.video.file_name or "video"
    if message.audio:
        return message.audio.file_name or message.audio.title or "audio"
    if message.photo:
        return f"photo_{message.id}.jpg"
    if message.animation:
        return message.animation.file_name or "animation"
    return f"file_{message.id}"
