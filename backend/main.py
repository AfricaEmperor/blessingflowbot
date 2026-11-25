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
from mission_store import active_mission, create_mission, update_mission, get_mission, record_proof, mission_proofs, generate_outcome, generate_next_mission
init_db()

LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "proofs.json")


def load_assets():
    fp = os.path.join(os.path.dirname(__file__), "blessings", "blessing_assets.json")
    with open(fp) as f:
        return json.load(f)


BLESSING_MAP = load_assets()


def log_proof(user_id, proof_hash, blessing, mission_id=None, verification_status="unverified"):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    entry = {
        "user_id": user_id,
        "hash": proof_hash,
        "blessing": blessing,
        "mission_id": mission_id,
        "verification_status": verification_status,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


STATIC = {
    "start": {
        "en": "🌊 Welcome to BlessingFlowBot. Use /flow to begin your ritual.",
        "fr": "🌊 Bienvenue. Tapez /flow pour commencer votre rituel.",
    },
    "help": {
        "en": "Commands: /flow, /proof <hash> [blessing], /mission [title] [objective] | /status | /outcome [mission_id] | /nextmission [mission_id] | /fr, /en.",
        "fr": "Commandes: /flow, /proof <hash> [bénédiction], /mission [titre] [objectif] | /status | /outcome [mission_id] | /nextmission [mission_id] | /fr, /en.",
    },
    "flow_fallback": {
        "en": "Send TON and type `/proof <hash>` to receive your blessing.",
        "fr": "Envoyez TON et tapez `/proof <hash>` pour recevoir votre bénédiction.",
    },
    "proof_fallback": {
        "en": "⚠️ Proof `{b}` recorded. The hash is not independently verified. Delivering your assets...",
        "fr": "⚠️ Preuve `{b}` enregistrée. Le hash n'est pas vérifié indépendamment. Livraison en cours...",
    },
    "unknown": {
        "en": "❓ Unknown command. Use /help.",
        "fr": "❓ Commande inconnue. Utilisez /help.",
    },
}


def _mission_text(mission):
    if not mission:
        return "No active mission. Create one with /mission <title> [objective]."
    blockers = mission.get("blockers") or "[]"
    try:
        blockers = ", ".join(json.loads(blockers)) or "None"
    except (TypeError, ValueError):
        blockers = str(blockers)
    proofs = mission_proofs(mission["mission_id"])
    return (
        f"🔥 {mission['mission_id']} — {mission['title']}\n"
        f"Objective: {mission['objective']}\nStatus: {mission['status']}\n"
        f"Channel: {mission['channel']}\nBlockers: {blockers}\n"
        f"Proof submissions: {len(proofs)} (not independently verified)\n"
        f"Next move: {mission['next_move'] or 'Not set'}"
    )


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


def mission_cmd(update: Update, context: CallbackContext):
    args = context.args or []
    if args and args[0].lower() == "close":
        if len(args) < 2:
            update.message.reply_text("Usage: /mission close FLAME-001")
            return
        closed = update_mission(args[1], status="closed", next_move="Review outcome and approve next mission")
        update.message.reply_text(_mission_text(closed) if closed else "Mission not found.")
        return
    if not args:
        update.message.reply_text(_mission_text(active_mission()))
        return
    title = args[0]
    objective = " ".join(args[1:]) if len(args) > 1 else title
    try:
        created = create_mission(title, objective=objective)
        update.message.reply_text("Mission created.\n" + _mission_text(created))
    except ValueError as exc:
        update.message.reply_text(str(exc))


def status_cmd(update: Update, context: CallbackContext):
    update.message.reply_text(_mission_text(active_mission()))


def outcome_cmd(update: Update, context: CallbackContext):
    mission_id = context.args[0] if context.args else (active_mission() or {}).get("mission_id")
    if not mission_id:
        update.message.reply_text("No active mission. Create one with /mission <title>.")
        return
    try:
        outcome = generate_outcome(mission_id)
    except ValueError as exc:
        update.message.reply_text(str(exc))
        return
    update.message.reply_text(
        f"📘 OUTCOME — {outcome['mission_id']}\n"
        f"Mission: {outcome['title']}\nObjective: {outcome['objective']}\n"
        f"Proof submissions: {outcome['proof_count']}\n"
        f"Verified: {outcome['verified_proofs']} | Unverified: {outcome['unverified_proofs']}\n"
        f"Evidence limitation: {outcome['evidence_limitations']}\n"
        f"Interpretation: {outcome['interpretation']}\nDecision: {outcome['decision']}"
    )


def nextmission_cmd(update: Update, context: CallbackContext):
    mission_id = context.args[0] if context.args else (active_mission() or {}).get("mission_id")
    if not mission_id:
        update.message.reply_text("No mission found. Create one with /mission <title>.")
        return
    try:
        proposal = generate_next_mission(mission_id)
    except ValueError as exc:
        update.message.reply_text(str(exc))
        return
    update.message.reply_text(
        f"🧭 NEXT MISSION PROPOSAL (requires human approval)\nParent: {proposal['parent_mission_id']}\n"
        f"Title: {proposal['title']}\nObjective: {proposal['objective']}\n"
        f"Channel: {proposal['channel']}\nStatus: {proposal['status']}"
    )


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
    proof_record = record_proof(uid, proof_hash, blessing)
    log_proof(uid, proof_hash, blessing, proof_record["mission_id"], proof_record["verification_status"])

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
dispatcher.add_handler(CommandHandler("mission", mission_cmd))
dispatcher.add_handler(CommandHandler("status", status_cmd))
dispatcher.add_handler(CommandHandler("outcome", outcome_cmd))
dispatcher.add_handler(CommandHandler("nextmission", nextmission_cmd))
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
