import requests

from config import BALE_BOT_TOKEN


def send_message(text, chat_id: int):
    resp = requests.post(
        f"https://tapi.bale.ai/bot{BALE_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
        },
    )
    resp_json = resp.json()
    print(resp_json)
    if (not resp_json["ok"]):
        raise Exception("Error sending message with bale bot")
