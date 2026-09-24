import pytest

from news_importance import _clean_text


def test_strips_bold_markers_and_emoji():
    text = "*🔴مسعود پزشکیان جهت ایراد سخنرانی وارد ساختمان سازمان ملل متحد شد*"
    assert (
        _clean_text(text)
        == "مسعود پزشکیان جهت ایراد سخنرانی وارد ساختمان سازمان ملل متحد شد"
    )


def test_strips_video_emoji_but_keeps_title():
    assert _clean_text("*🎥 سقوط جنگنده انگلیسی*") == "سقوط جنگنده انگلیسی"


@pytest.mark.parametrize(
    "text",
    [
        "وضعیت ایرانی‌ها در تنگه هرمز",
        "اختلال در فرود در فرودگاه بین‌المللی جده",
        "انفجار کنترل‌شدهٔ مهمات عمل‌نکردهٔ دشمن",
    ],
)
def test_preserves_persian_letters_and_zwnj(text):
    # نیم‌فاصله (U+200C) بخشی از واژهٔ فارسی است و نباید حذف شود.
    assert _clean_text(text) == text


def test_only_emoji_and_symbols_cleans_to_empty():
    assert _clean_text("🔴🎥 *~` |") == ""

