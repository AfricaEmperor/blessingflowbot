import os
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
response = requests.post(url, json={"url": WEBHOOK_URL})
print("Webhook set:", response.json())
