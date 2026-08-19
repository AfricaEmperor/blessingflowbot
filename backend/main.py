from fastapi import FastAPI, Request
from telegram import Update, Bot, constants
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext
import asyncio, os, json
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
app = FastAPI()
dispatcher = Dispatcher(bot=bot, update_queue=asyncio.Queue(), use_context=True)

from db.memory import init_db, get_history, save_exchange, get_lang, save_lang
init_db()

LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "proofs.json")


def load_assets():
    fp = os.path.join(os.path.dirname(__file__), "blessings", "blessing_assets.json")
    with open(fp) as f:
        return json.load(f)


BLESSING_MAP = load_assets()


def log_proof(user_id, proof_hash, blessing):
    entry = {"user_id": user_id, "hash": proof_hash, "blessing": blessing}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


STATIC = {
    "start": {
        "en": "🌊 Welcome to BlessingFlowBot. Use /flow to begin your ritual.",
        "fr": "🌊 Bienvenue. Tapez /flow pour commencer votre rituel.",
    },
    "help": {
        "en": "Commands: /flow, /proof <hash> [blessing], /fr, /en.",
        "fr": "Commandes: /flow, /proof <hash> [bénédiction], /fr, /en.",
    },
    "flow_fallback": {
        "en": "Send TON and type `/proof <hash>` to receive your blessing.",
        "fr": "Envoyez TON et tapez `/proof <hash>` pour recevoir votre bénédiction.",
    },
    "proof_fallback": {
        "en": "✅ Blessing `{b}` verified. Delivering your assets...",
        "fr": "✅ Bénédiction `{b}` vérifiée. Livraison en cours...",
    },
    "unknown": {
        "en": "❓ Unknown command. Use /help.",
        "fr": "❓ Commande inconnue. Utilisez /help.",
    },
}


def start(update: Update, context: CallbackContext):
    lang = get_lang(update.effective_user.id)
    update.message.reply_text(STATIC["start"][lang])


def flow(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    lang = get_lang(uid)
    try:
        from ai.portal_priest import get_flow_guidance
        text = get_flow_guidance(lang, get_history(uid))
        save_exchange(uid, "/flow", text)
    except Exception:
        text = STATIC["flow_fallback"][lang]
    update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN)


def help_cmd(update: Update, context: CallbackContext):
    lang = get_lang(update.effective_user.id)
    update.message.reply_text(STATIC["help"][lang])


def proof(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    lang = get_lang(uid)
    args = context.args
    if not args:
        update.message.reply_text(
            "❗ Provide the transaction hash: `/proof <hash>`.",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    proof_hash = args[0]
    blessing = args[1] if len(args) > 1 and args[1] in BLESSING_MAP else "flow"
    log_proof(uid, proof_hash, blessing)

    try:
        from ai.portal_priest import get_proof_blessing
        ritual_msg = get_proof_blessing(blessing, proof_hash, lang, get_history(uid))
        save_exchange(uid, f"/proof {proof_hash[:8]}...", ritual_msg)
    except Exception:
        ritual_msg = STATIC["proof_fallback"][lang].format(b=blessing)

    update.message.reply_text(ritual_msg, parse_mode=constants.ParseMode.MARKDOWN)

    from blessings.dispatcher import dispatch_blessing
    dispatch_blessing(bot, update.effective_chat.id, blessing, lang)


def switch_fr(update: Update, context: CallbackContext):
    save_lang(update.effective_user.id, "fr")
    update.message.reply_text("🇫🇷 Bot en français.")


def switch_en(update: Update, context: CallbackContext):
    save_lang(update.effective_user.id, "en")
    update.message.reply_text("🇬🇧 Bot in English.")


def handle_message(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    lang = get_lang(uid)
    user_text = update.message.text
    try:
        from ai.portal_priest import get_priest_response
        response = get_priest_response(user_text, get_history(uid))
        save_exchange(uid, user_text, response)
        update.message.reply_text(response)
    except Exception:
        update.message.reply_text(STATIC["unknown"][lang])


def fallback(update: Update, context: CallbackContext):
    lang = get_lang(update.effective_user.id)
    update.message.reply_text(STATIC["unknown"][lang])


dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("flow", flow))
dispatcher.add_handler(CommandHandler("help", help_cmd))
dispatcher.add_handler(CommandHandler("proof", proof))
dispatcher.add_handler(CommandHandler("fr", switch_fr))
dispatcher.add_handler(CommandHandler("en", switch_en))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
dispatcher.add_handler(MessageHandler(Filters.command, fallback))


@app.post("/bot")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, dispatcher.process_update, update)
    return {"status": "ok"}
