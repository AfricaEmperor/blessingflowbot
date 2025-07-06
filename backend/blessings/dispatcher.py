import os
from telegram import InputMediaPhoto, InputMediaAudio
import json

BASE = os.path.dirname(__file__)
ASSETS = os.path.join(os.path.dirname(BASE), "assets")

with open(os.path.join(BASE, "blessing_assets.json"), "r") as f:
    BLESSINGS = json.load(f)

def dispatch_blessing(bot, chat_id, blessing_key, lang):
    mapping = BLESSINGS.get(blessing_key, BLESSINGS["flow"])
    media = []
    qr_path = os.path.join(ASSETS, mapping["qr"])
    media.append(InputMediaPhoto(open(qr_path, "rb")))
    audio_path = os.path.join(ASSETS, mapping["audio"])
    media.append(InputMediaAudio(open(audio_path, "rb")))
    bot.send_media_group(chat_id=chat_id, media=media)
    scroll = mapping.get("scroll")
    if scroll:
        bot.send_document(chat_id=chat_id, document=open(os.path.join(ASSETS, scroll), "rb"))
