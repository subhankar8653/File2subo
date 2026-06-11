import sys
import asyncio
from datetime import datetime
from aiohttp import web
import pyromod.listen
from pyromod.listen import Client
from pyrogram.enums import ParseMode

from config import (
    API_ID, API_HASH, BOT_TOKEN, TG_BOT_WORKERS,
    FORCE_SUB_CHANNEL, LOG_CHANNEL, PORT, LOGGER
)
from plugins import web_server

log = LOGGER(__name__)


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
