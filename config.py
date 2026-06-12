import os
import logging
from logging.handlers import RotatingFileHandler

# ── Required ─────────────────────────────────────────────────────
API_ID       = int(os.environ.get("API_ID", "0"))
API_HASH     = os.environ.get("API_HASH", "")
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
OWNER_ID     = int(os.environ.get("OWNER_ID", "0"))
MONGO_URI    = os.environ.get("MONGO_URI", "")
LOG_CHANNEL  = int(os.environ.get("LOG_CHANNEL", "0"))   # Private channel where files are stored
PORT         = int(os.environ.get("PORT", "8080"))

# ── Optional ─────────────────────────────────────────────────────
DB_NAME           = os.environ.get("DB_NAME", "suhanifilebot")
TG_BOT_WORKERS    = int(os.environ.get("TG_BOT_WORKERS", "4"))
FORCE_SUB_CHANNEL = int(os.environ.get("FORCE_SUB_CHANNEL", "0"))
JOIN_REQUEST_ENABLE = os.environ.get("JOIN_REQUEST_ENABLED", None)
START_PIC         = os.environ.get("START_PIC", "")
START_MSG         = os.environ.get("START_MESSAGE", "Hello {first}!\n\n🔗 I store files privately. Send me a file link to get your files.\n👑 Admins can generate links via /genlink or /batch.")
FORCE_MSG         = os.environ.get("FORCE_SUB_MESSAGE", "Hello {first}!\n\n<b>Please join our channel first to use this bot.</b>")
CUSTOM_CAPTION    = os.environ.get("CUSTOM_CAPTION", None)
PROTECT_CONTENT   = os.environ.get("PROTECT_CONTENT", "False") == "True"
AUTO_DELETE_TIME  = int(os.environ.get("AUTO_DELETE_TIME", "0"))
AUTO_DELETE_MSG   = os.environ.get("AUTO_DELETE_MSG", "⚠️ This file will be deleted in <b>{time}</b>. Save it before that!")
AUTO_DEL_SUCCESS_MSG = os.environ.get("AUTO_DEL_SUCCESS_MSG", "✅ Your file has been deleted. Thank you for using our service.")
DISABLE_CHANNEL_BUTTON = os.environ.get("DISABLE_CHANNEL_BUTTON", "False") == "True"
BOT_STATS_TEXT    = "<b>BOT UPTIME</b>\n{uptime}"
USER_REPLY_TEXT   = os.environ.get("USER_REPLY_TEXT", "")

# ── Admins ───────────────────────────────────────────────────────
try:
    ADMINS = [int(x) for x in os.environ.get("ADMINS", "").split() if x]
except ValueError:
    raise Exception("ADMINS list mein valid integers hone chahiye.")
ADMINS.append(OWNER_ID)

# ── Logger ───────────────────────────────────────────────────────
LOG_FILE_NAME = "suhanifilebot.log"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE_NAME, maxBytes=50_000_000, backupCount=5),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
