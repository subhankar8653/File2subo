import sys
import asyncio
from datetime import datetime
from aiohttp import web
import pyromod.listen
from pyromod.listen import Client
from pyrogram.enums import ParseMode
from pyrogram.errors import PeerIdInvalid, FloodWait
from pyrogram import raw

from config import (
    API_ID, API_HASH, BOT_TOKEN, TG_BOT_WORKERS,
    FORCE_SUB_CHANNEL, LOG_CHANNEL, PORT, LOGGER
)
from plugins import web_server

log = LOGGER(__name__)


# ═══════════════════════════════════════════════════════════════
# DEEP PEER RESOLUTION
# Redeploy ke baad fresh session mein Pyrogram ko channels ka
# access_hash nahi hota. Yeh function raw API se woh data fetch
# karta hai taaki get_chat(), get_chat_member() etc. bina
# PeerIdInvalid ke kaam karein.
# ═══════════════════════════════════════════════════════════════

async def _force_resolve_peer(client: Client, channel_id: int) -> bool:
    """Channel ko raw API se resolve karo. True = success."""
    try:
        await client.resolve_peer(channel_id)
        return True
    except Exception:
        pass

    try:
        # Raw GetChannels — access_hash 0 bhi chalega bot ke liye
        channel_id_raw = -(channel_id + 1000000000000)  # -100XXXXX → XXXXX
        result = await client.invoke(
            raw.functions.channels.GetChannels(
                id=[raw.types.InputChannel(
                    channel_id=channel_id_raw,
                    access_hash=0
                )]
            )
        )
        if result and result.chats:
            return True
    except Exception:
        pass

    try:
        await client.get_chat(channel_id)
        return True
    except Exception:
        return False


async def _resolve_all_fsub_peers(client: Client):
    """Startup pe DB ke sabhi FSub channels resolve karo."""
    try:
        from database.database import get_fsub_channels
        fsubs = await get_fsub_channels()
        if not fsubs:
            return

        log.info(f"🔍 Resolving {len(fsubs)} FSub channel(s)...")
        for ch_id in fsubs:
            try:
                ok = await _force_resolve_peer(client, ch_id)
                if ok:
                    try:
                        chat = await client.get_chat(ch_id)
                        log.info(f"✅ Resolved: {ch_id} → {chat.title}")
                    except Exception:
                        log.info(f"✅ Resolved: {ch_id} (title fetch nahi hua)")
                else:
                    log.warning(f"⚠️  Could not resolve: {ch_id} — bot admin hai?")
            except FloodWait as e:
                log.warning(f"FloodWait {e.value}s on {ch_id} — waiting...")
                await asyncio.sleep(e.value)
                await _force_resolve_peer(client, ch_id)
            except Exception as e:
                log.warning(f"❌ Resolve error {ch_id}: {e}")
            await asyncio.sleep(0.3)  # Rate limit se bachao

        log.info("✅ FSub peer resolution complete.")
    except Exception as e:
        log.error(f"_resolve_all_fsub_peers error: {e}")


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="SuhaniFileBot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=TG_BOT_WORKERS,
            plugins={"root": "plugins"},
            in_memory=True,
        )
        self.LOGGER = LOGGER

    async def start(self):
        await super().start()
        self.uptime = datetime.now()
        me = await self.get_me()
        self.username = me.username

        # ── Verify DB Channel ──────────────────────────────────────
        try:
            db_channel = await self.get_chat(LOG_CHANNEL)
            self.db_channel = db_channel
            test = await self.send_message(chat_id=db_channel.id, text="✅ Bot started successfully!")
            await test.delete()
        except Exception as e:
            log.warning(e)
            log.warning(f"Bot ko LOG_CHANNEL ({LOG_CHANNEL}) mein admin banana padega! Check karo.")
            log.info("Bot stopped.")
            sys.exit()

        # ── Force Sub invite link cache ────────────────────────────
        if FORCE_SUB_CHANNEL:
            try:
                link = (await self.get_chat(FORCE_SUB_CHANNEL)).invite_link
                if not link:
                    await self.export_chat_invite_link(FORCE_SUB_CHANNEL)
                    link = (await self.get_chat(FORCE_SUB_CHANNEL)).invite_link
                self.invitelink = link
            except Exception as e:
                log.warning(e)
                log.warning(f"FORCE_SUB_CHANNEL ({FORCE_SUB_CHANNEL}) se invite link export nahi hua. Bot ko admin banao.")
                log.info("Bot stopped.")
                sys.exit()

        # ── Deep Peer Resolution for FSub channels ─────────────────
        # Redeploy ke baad fresh session mein FSub channels ka
        # access_hash nahi hota — yahi "info fetch nahi hua" ka
        # root cause hai. Startup pe resolve kar lo.
        await _resolve_all_fsub_peers(self)

        self.set_parse_mode(ParseMode.HTML)

        # ── Start web server ───────────────────────────────────────
        app = web.AppRunner(await web_server())
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()

        log.info(f"✅ Bot started: @{self.username}")
        log.info("🚀 Bot is fully operational!")

    async def stop(self, *args):
        await super().stop()
        log.info("Bot stopped.")
