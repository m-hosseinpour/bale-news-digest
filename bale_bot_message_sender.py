import requests

from config import BALE_BOT_TOKEN
from model import MediaKind

BALE_API_BASE = "https://tapi.bale.ai"

# روش ارسال بر اساس نوع ضمیمه. عکس و ویدیو و صدا با متد اختصاصی خودشان می‌آیند؛
# فایل ناشناخته به sendDocument می‌رود.
SEND_METHOD_BY_MEDIA_KIND = {
    MediaKind.PHOTO: ("sendPhoto", "photo"),
    MediaKind.VIDEO: ("sendVideo", "video"),
    MediaKind.AUDIO: ("sendAudio", "audio"),
    MediaKind.DOCUMENT: ("sendDocument", "document"),
}


def _post(method: str, payload: dict) -> dict:
    resp = requests.post(
        f"{BALE_API_BASE}/bot{BALE_BOT_TOKEN}/{method}",
        json=payload,
        timeout=120,
    )
    resp_json = resp.json()
    print(resp_json)
    if not resp_json.get("ok"):
        raise Exception(f"Error calling bale bot {method}: {resp_json}")
    return resp_json


def send_message(text: str, chat_id: int) -> dict:
    return _post(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
        },
    )


def send_media(media_url: str, media_kind: MediaKind, caption: str, chat_id: int) -> dict:
    """ضمیمه را همراه متن خلاصه می‌فرستد (بله خودش از URL دانلود می‌کند)."""
    method, field = SEND_METHOD_BY_MEDIA_KIND[media_kind]
    return _post(
        method,
        {
            "chat_id": chat_id,
            field: media_url,
            "caption": caption,
        },
    )


def send_post(text: str, media_url: str | None, media_kind: MediaKind | None, chat_id: int) -> dict:
    """اگر ضمیمه وجود داشت آن را با متن می‌فرستد، وگرنه پیام متنی."""
    if media_url and media_kind:
        return send_media(media_url, media_kind, text, chat_id)
    return send_message(text, chat_id)
