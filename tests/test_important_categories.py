import importlib

import pytest

import config
from config import DEFAULT_IMPORTANT_CATEGORIES, _env_categories
from model import NewsCategory

EXCLUDED_BY_DEFAULT = {
    NewsCategory.ADVERTISEMENT,
    NewsCategory.SPORTS,
    NewsCategory.CULTURE_ART,
}


def test_default_is_every_category_except_advertisement_sports_culture_art():
    assert set(DEFAULT_IMPORTANT_CATEGORIES) == set(NewsCategory) - EXCLUDED_BY_DEFAULT


def test_default_keeps_unknown_in():
    # unknown هم داخل لیست است تا خبری که مدل دسته‌بندی‌اش نکرده بی‌صدا حذف نشود.
    assert NewsCategory.UNKNOWN in DEFAULT_IMPORTANT_CATEGORIES


def test_default_has_no_duplicates():
    assert len(DEFAULT_IMPORTANT_CATEGORIES) == len(set(DEFAULT_IMPORTANT_CATEGORIES))


@pytest.mark.parametrize("value", [None, "", "   ", ",", " , "])
def test_missing_or_empty_value_falls_back_to_default(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("IMPORTANT_CATEGORIES", raising=False)
    else:
        monkeypatch.setenv("IMPORTANT_CATEGORIES", value)

    assert _env_categories("IMPORTANT_CATEGORIES", DEFAULT_IMPORTANT_CATEGORIES) == DEFAULT_IMPORTANT_CATEGORIES


def test_valid_list_is_parsed(monkeypatch):
    monkeypatch.setenv("IMPORTANT_CATEGORIES", "politics,economy")

    assert _env_categories("IMPORTANT_CATEGORIES", DEFAULT_IMPORTANT_CATEGORIES) == [
        NewsCategory.POLITICS,
        NewsCategory.ECONOMY,
    ]


def test_one_unknown_token_rejects_the_whole_value(monkeypatch, capsys):
    # یک تایپ اشتباه نباید فیلتر ارسال را نصفه اعمال کند؛ کل مقدار رد می‌شود.
    monkeypatch.setenv("IMPORTANT_CATEGORIES", "advertisement,foo")

    assert _env_categories("IMPORTANT_CATEGORIES", DEFAULT_IMPORTANT_CATEGORIES) == DEFAULT_IMPORTANT_CATEGORIES
    assert "foo" in capsys.readouterr().out


def test_case_whitespace_and_trailing_comma_are_tolerated(monkeypatch):
    monkeypatch.setenv("IMPORTANT_CATEGORIES", " WAR_CONFLICT , sports , ")

    assert _env_categories("IMPORTANT_CATEGORIES", DEFAULT_IMPORTANT_CATEGORIES) == [
        NewsCategory.WAR_CONFLICT,
        NewsCategory.SPORTS,
    ]


def test_duplicates_are_collapsed(monkeypatch):
    monkeypatch.setenv("IMPORTANT_CATEGORIES", "economy,economy")

    assert _env_categories("IMPORTANT_CATEGORIES", DEFAULT_IMPORTANT_CATEGORIES) == [
        NewsCategory.ECONOMY
    ]


def test_fallback_does_not_alias_the_default(monkeypatch):
    monkeypatch.setenv("IMPORTANT_CATEGORIES", "")

    resolved = _env_categories("IMPORTANT_CATEGORIES", DEFAULT_IMPORTANT_CATEGORIES)
    resolved.append(NewsCategory.SPORTS)

    assert NewsCategory.SPORTS not in DEFAULT_IMPORTANT_CATEGORIES


def test_constant_is_read_from_env(monkeypatch):
    """اتصال واقعی env به IMPORTANT_CATEGORIES را قفل می‌کند."""
    monkeypatch.setenv("IMPORTANT_CATEGORIES", "economy")
    try:
        reloaded = importlib.reload(config)
        assert reloaded.IMPORTANT_CATEGORIES == [NewsCategory.ECONOMY]
    finally:
        monkeypatch.delenv("IMPORTANT_CATEGORIES", raising=False)
        importlib.reload(config)
