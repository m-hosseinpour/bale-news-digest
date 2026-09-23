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

    @field_validator("category", mode="before")
    @classmethod
    def fallback_category(cls, v):
        if v is None or isinstance(v, NewsCategory):
            return v
        try:
            return NewsCategory(v)
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
