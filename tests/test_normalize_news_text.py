import pytest

from news_collector import normalize_news_text

# خط تبلیغاتی واقعی کانال: «A» بزرگ در mention، ولی اسلاگ کانال با حروف کوچک است.
REAL_PROMO = "@Akharinkhabar | akharinkhabar.ir"
SLUG = "akharinkhabar"


def test_strips_real_promo_line():
    text = f"تیتر خبر\nمتن کامل خبر\n{REAL_PROMO}"
    assert normalize_news_text(text, SLUG) == "تیتر خبر\nمتن کامل خبر"


def test_strips_promo_with_extra_spaces():
    text = f"خبر\n@Akharinkhabar   |   akharinkhabar.ir"
    assert normalize_news_text(text, SLUG) == "خبر"


def test_strips_lowercase_mention_too():
    text = f"خبر\n@akharinkhabar | akharinkhabar.ir"
    assert normalize_news_text(text, SLUG) == "خبر"


def test_strips_bare_mention():
    assert normalize_news_text("@Akharinkhabar خبر", SLUG) == "خبر"


def test_leaves_unrelated_text_alone():
    text = "خبر مهم دربارهٔ بانک مرکزی و بازار ارز — ۱۲٪ رشد"
    assert normalize_news_text(text, SLUG) == text


def test_leaves_other_channels_alone():
    text = "خبر\n@top_news_digest\ntop_news_digest.ir"
    assert normalize_news_text(text, SLUG) == text


def test_similar_slug_is_not_a_prefix_match():
    # @akharinkhabar_plus نباید با \b به‌عنوان کانال ما حذف شود.
    text = "خبر @akharinkhabar_plus"
    assert normalize_news_text(text, SLUG) == text


def test_works_for_another_slug():
    text = "خبر\n@Top_news_digest | top_news_digest.ir"
    assert normalize_news_text(text, "top_news_digest") == "خبر"


@pytest.mark.parametrize("text", ["", "   ", "\n\n"])
def test_blank_input(text):
    assert normalize_news_text(text, SLUG) == ""


def test_dot_in_slug_is_escaped():
    text = "خبر\n@my.channel | my.channel.ir"
    assert normalize_news_text(text, "my.channel") == "خبر"
