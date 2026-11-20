"""تاریخ و ساعت انتشار پست، به تقویم شمسی — تا مدل یک «حالا» داشته باشد.

بدون این، هیچ‌کدام از دو پرامپت نمی‌فهمد تاریخِ داخل متن خبر تازه است یا مال
ماه‌ها قبل: پستی که «ویدیوی تازه از حملهٔ ۱۷ فروردین» را منتشر می‌کند، هم در
سنجش اهمیت مثل خبر تازهٔ جنگ دیده می‌شود و هم در خلاصه به گزارشِ خودِ حمله
تبدیل می‌شود.

تاریخ از `date` خودِ API بله می‌آید (بخش دوم `sid`)، نه از ساعت اجرا؛ پس در
اجرای دوبارهٔ همان پست هم ثابت می‌ماند.
"""

from datetime import datetime, timedelta, timezone

# تهران از ۲۰۲۲ ساعت تابستانی ندارد؛ پس آفست ثابت است.
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

JALALI_MONTHS = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# طول ماه‌های میلادی تا پیش از ماه جاری، برای محاسبهٔ شمارهٔ روز در سال.
_GREGORIAN_DAYS_BEFORE_MONTH = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیل تاریخ میلادی به شمسی (الگوریتم بورکوفسکی، همان که jdatetime دارد).

    دقیق برای سال‌های میلادی ۱۶۰۱ به بعد — همان محدودهٔ jdatetime. شاخهٔ
    پیش از ۱۶۰۱ در این پیاده‌سازی دقیق نیست و از این ماژول هم هرگز صدا زده
    نمی‌شود: تاریخ پست‌ها همیشه معاصر است.
    """
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621

    gy2 = gy + 1 if gm > 2 else gy
    days = (
        365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        - 80
        + gd
        + _GREGORIAN_DAYS_BEFORE_MONTH[gm - 1]
    )

    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461

    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30

    return jy, jm, jd


def _persian_digits(text: str) -> str:
    return text.translate(_PERSIAN_DIGITS)


def format_post_time(date_ms: int) -> str:
    """زمان انتشار پست به شکل «۲۸ آبان ۱۴۰۵، ساعت ۱۷:۵۳ به وقت تهران (2026-11-19)»."""
    local = datetime.fromtimestamp(date_ms / 1000, tz=TEHRAN_TZ)
    jy, jm, jd = gregorian_to_jalali(local.year, local.month, local.day)
    jalali = f"{_persian_digits(str(jd))} {JALALI_MONTHS[jm - 1]} {_persian_digits(str(jy))}"
    clock = _persian_digits(local.strftime("%H:%M"))
    return f"{jalali}، ساعت {clock} به وقت تهران ({local:%Y-%m-%d})"
