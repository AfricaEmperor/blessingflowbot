from fastapi import FastAPI, Request
from telegram import Update, Bot, ParseMode
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext
import asyncio, os, json, logging
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
app = FastAPI()
dispatcher = Dispatcher(bot=bot, update_queue=asyncio.Queue(), use_context=True)

from db.memory import init_db, get_history, save_exchange, get_lang, save_lang
init_db()

logger = logging.getLogger("blessingflow")

try:
    from flame import service as flame
    from flame import render as flame_render
    from flame.config import is_admin as flame_is_admin
    from flame.errors import FlameError

    flame.init()
except Exception:  # mission tracking must never take the ritual flow down
    logger.exception("Flame Loop unavailable; continuing without mission tracking")
    flame = None

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
        "en": "Commands: /flow, /proof <hash> [blessing], /status, /fr, /en.",
        "fr": "Commandes: /flow, /proof <hash> [bénédiction], /status, /fr, /en.",
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


def _flame_record(user_id, proof_hash, blessing, lang):
    """Link the proof to the active mission. Never raises: the ritual comes first."""
    if flame is None:
        return None
    try:
        return flame.record_proof(user_id, proof_hash, blessing, lang)
    except Exception:
        logger.exception("could not record proof in the mission store")
        return None


def _flame_delivery(record, status, error=None):
    if flame is None or not record or record.get("duplicate"):
        return
    try:
        flame.set_delivery(record["proof_id"], status, error)
    except Exception:
        logger.exception("could not update delivery status")


def _dispatch_and_track(chat_id, blessing, lang, record):
    """Send the blessing assets; a failure is logged and recorded, not raised."""
    try:
        from blessings.dispatcher import dispatch_blessing

        dispatch_blessing(bot, chat_id, blessing, lang)
    except Exception as exc:
        logger.exception("blessing dispatch failed")
        _flame_delivery(record, "failed", f"{type(exc).__name__}: {exc}")
    else:
        _flame_delivery(record, "delivered")


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
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


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
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    proof_hash = args[0]
    blessing = args[1] if len(args) > 1 and args[1] in BLESSING_MAP else "flow"
    log_proof(uid, proof_hash, blessing)
    record = _flame_record(uid, proof_hash, blessing, lang)

    try:
        from ai.portal_priest import get_proof_blessing
        ritual_msg = get_proof_blessing(blessing, proof_hash, lang, get_history(uid))
        save_exchange(uid, f"/proof {proof_hash[:8]}...", ritual_msg)
    except Exception:
        ritual_msg = STATIC["proof_fallback"][lang].format(b=blessing)

    update.message.reply_text(ritual_msg, parse_mode=ParseMode.MARKDOWN)

    _dispatch_and_track(update.effective_chat.id, blessing, lang, record)


def status_cmd(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    lang = get_lang(uid)
    if flame is None:
        update.message.reply_text(STATIC["unknown"][lang])
        return
    try:
        admin = flame_is_admin(uid)
        snap = flame.snapshot()
        mine = None
        if snap["mission"] and not admin:
            mine = flame.user_proof_count(uid, snap["mission"]["id"])
        update.message.reply_text(flame_render.render_status(snap, lang, admin=admin, user_proofs=mine))
    except Exception:
        logger.exception("/status failed")
        update.message.reply_text(STATIC["unknown"][lang])


def outcome_cmd(update: Update, context: CallbackContext):
    """Admin only: show or generate the outcome of a closed mission."""
    uid = update.effective_user.id
    lang = get_lang(uid)
    if flame is None or not flame_is_admin(uid):
        update.message.reply_text(STATIC["unknown"][lang])
        return
    try:
        if context.args:
            mission_id = context.args[0]
        else:
            pending = flame.snapshot()["closed_without_outcome"]
            closed = [m["id"] for m in flame.list_missions() if m["status"] == "closed"]
            mission_id = (pending or closed or [None])[-1]
        if not mission_id:
            update.message.reply_text("No closed mission yet. Close one with: python -m flame.cli close <id>")
            return
        mission = flame.get_mission(mission_id)
        if mission and mission["status"] != "closed":
            update.message.reply_text(
                f"{mission_id} is {mission['status']}. Close it first: python -m flame.cli close {mission_id}"
            )
            return
        out = flame.generate_outcome(mission_id)
        nxt = flame.get_mission(out["next_mission_id"]) if out["next_mission_id"] else None
        update.message.reply_text(flame_render.render_outcome(out, mission, nxt))
    except FlameError as exc:
        update.message.reply_text(str(exc))
    except Exception:
        logger.exception("/outcome failed")
        update.message.reply_text(STATIC["unknown"][lang])


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
dispatcher.add_handler(CommandHandler("status", status_cmd))
dispatcher.add_handler(CommandHandler("outcome", outcome_cmd))
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
