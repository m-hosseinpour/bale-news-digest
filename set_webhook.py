import os

import requests
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")
PUBLIC_WEBHOOK_URL = os.getenv("PUBLIC_WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("BALE_WEBHOOK_SECRET", "")

if not BOT_TOKEN:
    raise RuntimeError("BALE_BOT_TOKEN is not set")

if not PUBLIC_WEBHOOK_URL:
    raise RuntimeError("PUBLIC_WEBHOOK_URL is not set")


url = f"https://tapi.bale.ai/bot{BOT_TOKEN}/setWebhook"

payload = {
    "url": PUBLIC_WEBHOOK_URL,
}

# فقط اگر secret گذاشتی، اضافه کن
if WEBHOOK_SECRET:
    payload["secret_token"] = WEBHOOK_SECRET

response = requests.post(url, json=payload, timeout=20)

print(response.status_code)
print(response.text)
