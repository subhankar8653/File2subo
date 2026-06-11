"""
plugins/fsub.py
───────────────
Force Subscribe + Fake Link commands.

Commands (Admin only):
  /addsub   <channel_id>        — FSub channel add karo
  /removesub <channel_id>       — FSub channel hata do
  /listsub                      — Sabhi FSub channels dekho

  /setfakelink <url> <text>     — Fake link button set karo (FSub message mein sabse pehle dikhta hai)
  /removefakelink               — Fake link hata do
  /viewfakelink                 — Current fake link dekho
"""

from pyrogram import filters
from pyrogram.types import Message

from bot import Bot
from config import ADMINS
from database.database import (
    add_fsub, remove_fsub, get_fsub_channels,
    set_fake_link, get_fake_link, remove_fake_link,
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
    Usage: /setfakelink <url> <button_text>
    Example: /setfakelink https://t.me/mychannel Join Mera Channel

    Yeh button FSub message mein sabse pehle position pe dikhega.
    Kaam: user ko ek fake/extra button dikhana jisko join karne ki zarurat nahi hoti —
    lekin join button ki tarah lagta hai (ad channel, sponsor link, etc.)
    """
    parts = message.text.split(maxsplit=2)

    if len(parts) < 3:
        return await message.reply(
            "<b>❌ Galat format!</b>\n\n"
            "<b>Usage:</b>\n"
            "<code>/setfakelink [URL] [Button Text]</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/setfakelink https://t.me/mychannel Join Mera Channel</code>\n\n"
            "<i>💡 Yeh button FSub message mein sabse pehle dikhega.</i>"
        )

    url         = parts[1]
    button_text = parts[2]

    if not url.startswith(("http://", "https://", "t.me/")):
        return await message.reply(
            "❌ <b>Invalid URL!</b>\n\n"
            "URL <code>http://</code>, <code>https://</code> ya <code>t.me/</code> se shuru hona chahiye."
        )

    success = await set_fake_link(url, button_text)

    if success:
        await message.reply(
            "✅ <b>Fake Link set ho gaya!</b>\n\n"
            f"<b>Button Text:</b> <code>{button_text}</code>\n"
            f"<b>URL:</b> <code>{url}</code>\n\n"
            "<i>Yeh button FSub message mein sabse pehle position pe dikhega.</i>"
        )
    else:
        await message.reply("❌ <b>Error!</b> Fake link save nahi hua. Dobara try karo.")


# ── /removefakelink ───────────────────────────────────────────────

@Bot.on_message(filters.command("removefakelink") & filters.private & filters.user(ADMINS))
async def cmd_removefakelink(client: Bot, message: Message):
    """Remove the currently set fake link."""
    success = await remove_fake_link()

    if success:
        await message.reply(
            "✅ <b>Fake Link hata diya!</b>\n\n"
            "<i>Ab FSub message mein fake link button nahi dikhega.</i>"
        )
    else:
        await message.reply("❌ <b>Koi fake link set nahi hai!</b>")


# ── /viewfakelink ─────────────────────────────────────────────────

@Bot.on_message(filters.command("viewfakelink") & filters.private & filters.user(ADMINS))
async def cmd_viewfakelink(client: Bot, message: Message):
    """View the currently configured fake link."""
    fake = await get_fake_link()

    if fake:
        await message.reply(
            "📝 <b>Current Fake Link Settings:</b>\n\n"
            f"<b>Button Text:</b> <code>{fake['button_text']}</code>\n"
            f"<b>URL:</b> <code>{fake['url']}</code>\n\n"
            "<i>Yeh button FSub message mein sabse pehle position pe dikhta hai.</i>"
        )
    else:
        await message.reply(
            "❌ <b>Koi fake link set nahi hai.</b>\n\n"
            "Set karne ke liye:\n"
            "<code>/setfakelink https://t.me/channel Button Text</code>"
        )
