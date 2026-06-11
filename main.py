import asyncio
import sys
from aiohttp import web
from config import PORT, LOGGER, MONGO_URI
from bot import app

log = LOGGER(__name__)

async def health_check(request):
    return web.Response(text="OK")

async def start_web():
    server = web.Application()
    server.router.add_get("/", health_check)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info(f"Health check server started on port {PORT}")

async def main():
    # Test MongoDB
    from motor.motor_asyncio import AsyncIOMotorClient
    try:
        client = AsyncIOMotorClient(MONGO_URI)
        await client.admin.command("ping")
        log.info("✅ MongoDB connected")
    except Exception as e:
        log.error(f"❌ MongoDB failed: {e}")
        sys.exit(1)

    # Start web server
    asyncio.create_task(start_web())

    # Start bot
    await app.start()
    me = await app.get_me()
    log.info(f"✅ Bot started: @{me.username}")

    # Set commands
    from pyrogram.types import BotCommand
    await app.set_bot_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("genlink", "Generate link for a file"),
        BotCommand("batch", "Generate batch link"),
        BotCommand("stats", "Bot statistics"),
        BotCommand("broadcast", "Broadcast a message"),
        BotCommand("addadmin", "Add admin"),
        BotCommand("removeadmin", "Remove admin"),
        BotCommand("ban", "Ban a user"),
        BotCommand("unban", "Unban a user"),
        BotCommand("addsub", "Add force subscribe channel"),
        BotCommand("removesub", "Remove force subscribe channel"),
        BotCommand("protect", "Toggle content protection"),
    ])

    log.info("🚀 Bot is fully operational!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot stopped.")
