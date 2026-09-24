from enum import Enum

from pydantic import BaseModel, field_validator


class NewsCategory(str, Enum):
    WAR_CONFLICT = "war_conflict"
    ADVERTISEMENT = "advertisement"
    POLITICS = "politics"
    ECONOMY = "economy"
    SOCIAL = "social"
    SPORTS = "sports"
    CULTURE_ART = "culture_art"
    SCIENCE_TECH = "science_tech"
    UNKNOWN = "unknown"  # fallback


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


class NewsPost(BaseModel):
    sid: str
    text: str
    category: NewsCategory | None
    media_url: str | None = None
    media_kind: MediaKind | None = None
    # None یعنی اهمیت سنجیده نشده: یا پست در دستهٔ مهم نبوده، یا سنجش شکست
    # خورده. برای دستهٔ غیرمهم اصلاً ارسالی در کار نیست؛ در حالت شکست، هنگام
    # ارسال fail-open رفتار می‌کنیم تا خرابی گیتوی خبر را بی‌صدا حذف نکند.
    importance: Importance | None = None

    @field_validator("category", mode="before")
    @classmethod
    def fallback_category(cls, v):
        if v is None or isinstance(v, NewsCategory):
            return v
        try:
            return NewsCategory(v)
        except ValueError:
            return None

    @field_validator("importance", mode="before")
    @classmethod
    def fallback_importance(cls, v):
        if v is None or isinstance(v, Importance):
            return v
        try:
            return Importance(v)
        except ValueError:
            return None

    @field_validator("media_kind", mode="before")
    @classmethod
    def fallback_media_kind(cls, v):
        if v is None or isinstance(v, MediaKind):
            return v
        try:
            return MediaKind(v)
        except ValueError:
            return None
