import os
import logging

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bale-webhook")

BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("BALE_WEBHOOK_SECRET", "")

if not BOT_TOKEN:
    raise RuntimeError("BALE_BOT_TOKEN is not set")


FIXED_RESPONSE = """سلام! 👋

من در پیام خصوصی پاسخی نمی‌دهم و فقط خلاصهٔ اخبار مهم را در کانال @top_news_digest منتشر می‌کنم.

برای دریافت خلاصهٔ اخبار، لطفاً در این کانال عضو شوید:
🆔 @top_news_digest
🔗 https://ble.ir/top_news_digest
"""


app = Flask(__name__)


def send_message(chat_id: int | str, text: str) -> None:
    url = f"https://tapi.bale.ai/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        response_json = response.json()

        if not response_json.get("ok"):
            logger.error("Error sending message: %s", response_json)
        else:
            logger.info("Message sent to chat_id=%s", chat_id)

    except Exception as e:
        logger.error("Exception while sending message: %s", e)


def is_valid_secret(request_headers) -> bool:
    """
    اگر BALE_WEBHOOK_SECRET خالی باشد، بررسی secret انجام نمی‌شود.

    اگر مقدار داشته باشد، انتظار داریم پلتفرم بله همان secret را در هدر بفرستد.
    """
    if not WEBHOOK_SECRET:
        return True

    header_secret = (
            request_headers.get("X-Telegram-Bot-Api-Secret-Token")
            or request_headers.get("X-Bale-Bot-Api-Secret-Token")
            or ""
    )

    return header_secret == WEBHOOK_SECRET


@app.route("/webhook", methods=["POST"])
def webhook():
    if not is_valid_secret(request.headers):
        logger.warning("Invalid webhook secret received")
        return jsonify({"ok": False, "error": "forbidden"}), 403

    update = request.get_json(silent=True) or {}

    # فقط پیام‌های جدید message را بررسی می‌کنیم
    message = update.get("message")

    # اگر channel_post، edited_message و غیره بود، نادیده بگیر
    if not message:
        return jsonify({"ok": True})

    chat = message.get("chat") or {}
    chat_type = chat.get("type")
    chat_id = chat.get("id")

    # فقط PV؛ کانال و گروه نادیده گرفته می‌شوند
    if chat_type != "private":
        logger.info("Ignoring non-private message. chat_type=%s", chat_type)
        return jsonify({"ok": True})

    # پیام‌های سرویسی مثل عضو شدن/خارج شدن کسی را هم نادیده بگیر
    if "new_chat_members" in message or "left_chat_member" in message:
        return jsonify({"ok": True})

    logger.info("Received private message from chat_id=%s", chat_id)

    if chat_id is not None:
        send_message(chat_id, FIXED_RESPONSE)

    # حتی اگر ارسال پیام خطا داشت، به webhook پاسخ ok می‌دهیم
    # تا پلتفرم مدام آن را retry نکند
    return jsonify({"ok": True})


@app.route("/health", methods=["GET"])
def health():
    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
