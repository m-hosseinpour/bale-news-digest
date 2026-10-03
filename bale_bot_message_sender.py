import requests

from config import BALE_BOT_TOKEN
from model import MediaItem, MediaKind

BALE_API_BASE = "https://tapi.bale.ai"

# روش ارسال بر اساس نوع ضمیمه. عکس و ویدیو و صدا با متد اختصاصی خودشان می‌آیند؛
# فایل ناشناخته به sendDocument می‌رود.
SEND_METHOD_BY_MEDIA_KIND = {
    MediaKind.PHOTO: ("sendPhoto", "photo"),
    MediaKind.VIDEO: ("sendVideo", "video"),
    MediaKind.AUDIO: ("sendAudio", "audio"),
    MediaKind.DOCUMENT: ("sendDocument", "document"),
}

# نوع قلم در آرایهٔ media برای sendMediaGroup. سند و صوت گروه نمی‌شوند.
GROUP_TYPE_BY_MEDIA_KIND = {
    MediaKind.PHOTO: "photo",
    MediaKind.VIDEO: "video",
}

# سقف واقعی بله برای یک آلبوم؛ ۱۱ قلم با «malformed request» رد می‌شود.
MAX_MEDIA_GROUP_SIZE = 10


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


def send_media_group(items: list[MediaItem], caption: str, chat_id: int) -> dict:
    """آلبوم را در یک پیام می‌فرستد؛ کپشن روی قلم اول می‌نشیند.

    media باید آرایهٔ واقعی JSON باشد؛ فرستادنش به‌صورت رشتهٔ JSON با خطای
    «malformed request» رد می‌شود (تست زنده).
    """
    media = []
    for index, item in enumerate(items):
        group_type = GROUP_TYPE_BY_MEDIA_KIND.get(item.kind)
        if group_type is None:
            raise ValueError(
                f"⛔ نوع {item.kind.value} در آلبوم پشتیبانی نمی‌شود (فقط عکس و ویدیو)."
            )
        entry: dict = {"type": group_type, "media": item.url}
        if index == 0 and caption:
            entry["caption"] = caption
        media.append(entry)

    return _post("sendMediaGroup", {"chat_id": chat_id, "media": media})


def _chunk_sizes(total: int) -> list[int]:
    """اندازهٔ تکه‌های آلبوم، پخش‌شده و بدون تکهٔ تک‌قلمی.

    تکه‌بندی سادهٔ «هر ۱۰ قلم» برای ۱۱ قلم [۱۰, ۱] می‌دهد و بله آلبوم تک‌قلمی
    را با «malformed request» رد می‌کند؛ پس ۱۱ قلم [۶, ۵] می‌شود.
    """
    chunk_count = -(-total // MAX_MEDIA_GROUP_SIZE)
    base, remainder = divmod(total, chunk_count)
    return [base + 1] * remainder + [base] * (chunk_count - remainder)


def send_post(text: str, media: list[MediaItem], chat_id: int) -> dict:
    """ضمیمه‌ها را با متن می‌فرستد: تک‌قلم با متد خودش، آلبوم با sendMediaGroup."""
    if not media:
        return send_message(text, chat_id)

    if len(media) == 1:
        return send_media(media[0].url, media[0].kind, text, chat_id)

    # آلبوم مبدأ حداکثر ۱۰ قلم است، ولی اگر گروه‌بندی دو آلبوم را به هم بچسباند
    # سقف بله رد می‌شود؛ پس تکه‌تکه می‌فرستیم و کپشن روی تکهٔ اول می‌ماند.
    chunks: list[list[MediaItem]] = []
    start = 0
    for size in _chunk_sizes(len(media)):
        chunks.append(media[start : start + size])
        start += size

    response: dict = {}
    for index, chunk in enumerate(chunks):
        response = send_media_group(chunk, text if index == 0 else "", chat_id)
    return response
