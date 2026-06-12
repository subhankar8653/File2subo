"""
plugins/fsub.py
───────────────
Force Subscribe + Fake Link commands.

Commands (Admin only):
  /addsub   <channel_id>        — FSub channel add karo
  /removesub <channel_id>       — FSub channel hata do
  /listsub                      — Sabhi FSub channels dekho

  /setfakelink <url> <text> [row]  — Fake link button add karo (row optional, default 1)
  /deletefakelink <number>         — Fake link delete karo (/listfakelink se number lo)
  /listfakelink                    — Sabhi fake links dekho
"""

from pyrogram import filters
from pyrogram.types import Message

from bot import Bot
from config import ADMINS
from database.database import (
    add_fsub, remove_fsub, get_fsub_channels,
    add_fake_link, get_fake_links, remove_fake_link_by_index,
)


# ── /addsub ───────────────────────────────────────────────────────

@Bot.on_message(filters.command("addsub") & filters.private & filters.user(ADMINS))
async def cmd_addsub(client: Bot, message: Message):
    """
    Usage: /addsub <channel_id>
    Example: /addsub -1001234567890
    """
    if len(message.command) < 2:
        return await message.reply(
            "<b>❌ Usage:</b> <code>/addsub &lt;channel_id&gt;</code>\n\n"
            "<b>Example:</b> <code>/addsub -1001234567890</code>"
        )
    try:
        ch_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Channel ID valid integer hona chahiye.")

    await add_fsub(ch_id)

    # Channel title fetch karne ki koshish karo
    try:
        chat = await client.get_chat(ch_id)
        name = chat.title
    except Exception:
        name = str(ch_id)

    await message.reply(
        f"✅ <b>Force Sub channel add ho gaya!</b>\n\n"
        f"📢 <b>Channel:</b> {name}\n"
        f"🆔 <b>ID:</b> <code>{ch_id}</code>"
    )


# ── /removesub ────────────────────────────────────────────────────

@Bot.on_message(filters.command("removesub") & filters.private & filters.user(ADMINS))
async def cmd_removesub(client: Bot, message: Message):
    """
    Usage: /removesub <channel_id>
    """
    if len(message.command) < 2:
        return await message.reply(
            "<b>❌ Usage:</b> <code>/removesub &lt;channel_id&gt;</code>\n\n"
            "<b>Example:</b> <code>/removesub -1001234567890</code>"
        )
    try:
        ch_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Channel ID valid integer hona chahiye.")

    await remove_fsub(ch_id)
    await message.reply(
        f"✅ <b>Force Sub channel hata diya!</b>\n"
        f"🆔 <code>{ch_id}</code>"
    )


# ── /listsub ──────────────────────────────────────────────────────

@Bot.on_message(filters.command("listsub") & filters.private & filters.user(ADMINS))
async def cmd_listsub(client: Bot, message: Message):
    """List all active FSub channels."""
    fsubs = await get_fsub_channels()

    if not fsubs:
        return await message.reply("📢 <b>Koi Force Sub channel set nahi hai.</b>")

    lines = ["<b>📢 Force Sub Channels:</b>\n"]
    for i, ch_id in enumerate(fsubs, 1):
        try:
            chat = await client.get_chat(ch_id)
            title = chat.title
            link  = f"https://t.me/{chat.username}" if chat.username else "—"
            lines.append(f"{i}. <b>{title}</b>\n   🆔 <code>{ch_id}</code>  🔗 {link}")
        except Exception:
            lines.append(f"{i}. <code>{ch_id}</code> (info fetch nahi hua)")

    lines.append(f"\n<b>Total:</b> {len(fsubs)}")
    await message.reply("\n".join(lines))


# ═══════════════════════════════════════════════════════════════════
# FAKE LINK COMMANDS
# ═══════════════════════════════════════════════════════════════════

# ── /setfakelink ──────────────────────────────────────────────────

@Bot.on_message(filters.command("setfakelink") & filters.private & filters.user(ADMINS))
async def cmd_setfakelink(client: Bot, message: Message):
    """
    Usage: /setfakelink <url> <button_text> [row]
    Example: /setfakelink https://t.me/mychannel Join Mera Channel 2

    Multiple fake links add kar sakte ho — purana delete nahi hoga.
    Row batata hai ki button kaunsi position pe FSub message mein dikhega
    (1 = sabse pehla, 2 = dusra, etc.)
    """
    parts = message.text.split(maxsplit=2)

    if len(parts) < 3:
        return await message.reply(
            "<b>❌ Galat format!</b>\n\n"
            "<b>Usage:</b>\n"
            "<code>/setfakelink [URL] [Button Text] [Row]</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/setfakelink https://t.me/mychannel Join Mera Channel 2</code>\n\n"
            "<i>💡 Row optional hai (default 1). Row 2 ka matlab — yeh button "
            "FSub message mein 2nd position pe dikhega.</i>"
        )

    url  = parts[1]
    rest = parts[2]

    # Last word ko row number ke liye check karo (agar integer hai)
    row = 1
    rest_parts = rest.rsplit(maxsplit=1)
    if len(rest_parts) == 2 and rest_parts[1].isdigit():
        button_text = rest_parts[0]
        row = max(1, int(rest_parts[1]))
    else:
        button_text = rest

    if not url.startswith(("http://", "https://", "t.me/")):
        return await message.reply(
            "❌ <b>Invalid URL!</b>\n\n"
            "URL <code>http://</code>, <code>https://</code> ya <code>t.me/</code> se shuru hona chahiye."
        )

    success = await add_fake_link(url, button_text, row)

    if success:
        await message.reply(
            "✅ <b>Fake Link add ho gaya!</b>\n\n"
            f"<b>Button Text:</b> <code>{button_text}</code>\n"
            f"<b>URL:</b> <code>{url}</code>\n"
            f"<b>Row:</b> <code>{row}</code>\n\n"
            "<i>Yeh button FSub message mein position</i> "
            f"<i>{row} pe dikhega. List dekhne ke liye /listfakelink.</i>"
        )
    else:
        await message.reply("❌ <b>Error!</b> Fake link save nahi hua. Dobara try karo.")


# ── /deletefakelink ───────────────────────────────────────────────

@Bot.on_message(filters.command("deletefakelink") & filters.private & filters.user(ADMINS))
async def cmd_deletefakelink(client: Bot, message: Message):
    """
    Usage: /deletefakelink <number>
    Example: /deletefakelink 1

    Number /listfakelink se lo.
    """
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply(
            "<b>❌ Usage:</b> <code>/deletefakelink [number]</code>\n\n"
            "Number dekhne ke liye <code>/listfakelink</code> use karo."
        )

    index = int(message.command[1])
    success = await remove_fake_link_by_index(index)

    if success:
        await message.reply(
            f"✅ <b>Fake Link #{index} hata diya!</b>\n\n"
            "<i>Baki fake links jaise the waise hi hai.</i>"
        )
    else:
        await message.reply(f"❌ <b>Fake Link #{index} nahi mila!</b>")


# ── /listfakelink ─────────────────────────────────────────────────

@Bot.on_message(filters.command("listfakelink") & filters.private & filters.user(ADMINS))
async def cmd_listfakelink(client: Bot, message: Message):
    """View all configured fake links."""
    fakes = await get_fake_links()

    if not fakes:
        return await message.reply(
            "❌ <b>Koi fake link set nahi hai.</b>\n\n"
            "Set karne ke liye:\n"
            "<code>/setfakelink https://t.me/channel Button Text [row]</code>"
        )

    lines = ["📝 <b>Fake Links:</b>\n"]
    for i, fake in enumerate(fakes, 1):
        lines.append(
            f"<b>{i}.</b> <code>{fake['button_text']}</code>\n"
            f"   🔗 <code>{fake['url']}</code>\n"
            f"   📍 Row: <code>{fake['row']}</code>"
        )

    lines.append("\n<i>Delete karne ke liye: /deletefakelink (number)</i>")
    await message.reply("\n\n".join(lines))
