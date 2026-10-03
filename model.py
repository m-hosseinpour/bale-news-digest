from enum import Enum

from pydantic import BaseModel, field_validator


class Importance(str, Enum):
    """اهمیت خبر برای مخاطبی که وقت کمی دارد. ترتیب با IMPORTANCE_RANK."""

    MAJOR = "major"
    NORMAL = "normal"
    TRIVIAL = "trivial"


# رتبهٔ ترتیبی برای مقایسه با آستانهٔ ارسال. MAJOR بالاترین اهمیت است.
IMPORTANCE_RANK: dict[Importance, int] = {
    Importance.TRIVIAL: 1,
    Importance.NORMAL: 2,
    Importance.MAJOR: 3,
}


class MediaKind(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


class MediaItem(BaseModel):
    """یک ضمیمهٔ پست. url لینک امضاشدهٔ عمومی است؛ file_id وجود ندارد."""

    url: str
    kind: MediaKind


class NewsPost(BaseModel):
    sid: str
    text: str
    # آلبوم چند قلم دارد و به ترتیب کانال مبدأ می‌آید (قلم دارای کپشن اول).
    media: list[MediaItem] = []
    # None یعنی سنجش شکست خورد (بعد از چند تلاش پاسخ قابل استفاده نبود).
    # در این حالت هنگام ارسال fail-open رفتار می‌کنیم تا خرابی گیتوی خبر را
    # بی‌صدا حذف نکند. متن بدون محتوا اینجا نمی‌رسد: collector آن را trivial
    # می‌کند تا با fail-open به کانال نرود.
    importance: Importance | None = None

    @field_validator("importance", mode="before")
    @classmethod
    def fallback_importance(cls, v):
        if v is None or isinstance(v, Importance):
            return v
        try:
            return Importance(v)
        except ValueError:
            return None

    @property
    def media_kind(self) -> MediaKind | None:
        """نوع قلم اول — برای برچسب ضمیمه در خلاصه‌سازی، نه برای ارسال."""
        return self.media[0].kind if self.media else None
