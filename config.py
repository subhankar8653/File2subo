import os
import logging

# ── Required Variables ──────────────────────────────────────────
API_ID       = int(os.environ.get("API_ID", "0"))
API_HASH     = os.environ.get("API_HASH", "")
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
OWNER_ID     = int(os.environ.get("OWNER_ID", "0"))
MONGO_URI    = os.environ.get("MONGO_URI", "")
LOG_CHANNEL  = int(os.environ.get("LOG_CHANNEL", "0"))   # Private channel ID where files are stored
PORT         = int(os.environ.get("PORT", "8080"))

# ── Optional ────────────────────────────────────────────────────
DB_NAME      = os.environ.get("DB_NAME", "suhanifilebot")

# ── Logger ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)
def LOGGER(name): return logging.getLogger(name)
