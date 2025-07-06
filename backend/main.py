from fastapi import FastAPI, Request
from telegram import Update, Bot, constants
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext
import asyncio, os, json

# Bot & FastAPI setup
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
bot = Bot(token=BOT_TOKEN)
app = FastAPI()
dispatcher = Dispatcher(bot=bot, update_queue=asyncio.Queue(), use_context=True)

# Language state
user_lang = {}

def get_lang(uid): return user_lang.get(uid, "en")
def set_lang(uid, lang): user_lang[uid] = lang

# Load blessing assets map
def load_assets():
    fp = os.path.join(os.path.dirname(__file__), "blessings", "blessing_assets.json")
    with open(fp, "r") as f:
        return json.load(f)

BLESSING_MAP = load_assets()

# Simple logger
LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "proofs.json")

def log_proof(user_id, proof_hash, blessing):
    entry = {"user_id": user_id, "hash": proof_hash, "blessing": blessing}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

# Reply helper
def reply(update, key, markdown=False):
    uid = update.effective_user.id
    text = MESSAGES[key][get_lang(uid)]
    update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN if markdown else None)

# Predefined messages
MESSAGES = {
    "start": {"en": "🌊 Welcome to BlessingFlowBot. Use /flow to begin.",
              "fr": "🌊 Bienvenue. Tapez /flow pour commencer."},
    "flow":  {"en": "Send TON and type `/proof <hash>` to receive your blessing.",
              "fr": "Envoyez TON et tapez `/proof <hash>` pour recevoir votre bénédiction."},
    "help":  {"en": "Commands: /flow, /proof <hash>, /fr, /en.",
              "fr": "Commandes: /flow, /proof <hash>, /fr, /en."}
}

# Command handlers
def start(update: Update, context: CallbackContext): reply(update, "start")
def flow(update: Update, context: CallbackContext): reply(update, "flow")
def help_cmd(update: Update, context: CallbackContext): reply(update, "help")

def proof(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    args = context.args
    if not args:
        update.message.reply_text("❗ Please provide the transaction hash: `/proof <hash>`.",
                                  parse_mode=constants.ParseMode.MARKDOWN)
        return
    proof_hash = args[0]
    blessing = args[1] if len(args) > 1 and args[1] in BLESSING_MAP else "flow"

    # Log the proof submission
    log_proof(uid, proof_hash, blessing)

    # Acknowledge
    update.message.reply_text(f"✅ Blessing verified. Delivering your `{blessing}` blessing...",
                              parse_mode=constants.ParseMode.MARKDOWN)

    # Dispatch assets
    from blessings.dispatcher import dispatch_blessing
    dispatch_blessing(bot, update.effective_chat.id, blessing, get_lang(uid))

# Language switches
def switch_fr(update: Update, context: CallbackContext):
    set_lang(update.effective_user.id, "fr")
    update.message.reply_text("🇫🇷 Bot en français.")

def switch_en(update: Update, context: CallbackContext):
    set_lang(update.effective_user.id, "en")
    update.message.reply_text("🇬🇧 Bot in English.")

def fallback(update: Update, context: CallbackContext):
    update.message.reply_text("❓ Unknown command. Use /help.")

# Register handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("flow", flow))
dispatcher.add_handler(CommandHandler("help", help_cmd))
dispatcher.add_handler(CommandHandler("proof", proof))
dispatcher.add_handler(CommandHandler("fr", switch_fr))
dispatcher.add_handler(CommandHandler("en", switch_en))
dispatcher.add_handler(MessageHandler(Filters.command, fallback))

# Webhook receiver
@app.post("/bot")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return {"status": "ok"}
