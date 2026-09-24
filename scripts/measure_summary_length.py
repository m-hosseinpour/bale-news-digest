"""اندازه‌گیری طول خلاصه روی پست‌های واقعی ذخیره‌شده — برای مقایسهٔ A/B پرامپت.

نمونه‌ای تصادفی از پست‌های news_posts.json برمی‌دارد و هر کدام را چند بار از
مسیر واقعی (summarize_single_post) می‌گذراند و طول/تعداد جمله و میزان حفظ
عدد‌های متن اصلی را ثبت می‌کند. گیتوی مدل‌ها را round-robin می‌کند، پس نتیجه
نویزی است؛ برای همین هر پست چند بار اجرا می‌شود و مقایسه با میانه انجام می‌شود.

    uv run python scripts/measure_summary_length.py --out measurements/before.json
"""

import argparse
import hashlib
import json
import random
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model import NewsPost  # noqa: E402
from news_summarizer import (  # noqa: E402
    SHORT_TEXT_THRESHOLD,
    SYSTEM_PROMPT,
    summarize_single_post,
)

POSTS_PATH = Path("news_posts.json")

# اثر انگشت پرامپت در هر ردیف ثبت می‌شود تا دو اجرا با پرامپت‌های متفاوت اشتباهی
# با هم مقایسه نشوند.
PROMPT_HASH = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12]

# رقم لاتین و فارسی/عربی، به‌صورت دنباله‌ای از ارقام (نه رقم‌های پراکنده).
_DIGITS_RE = re.compile(r"[0-9۰-۹٠-٩]+")
_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_SENTENCE_SPLIT_RE = re.compile(r"[.؟?!\n]+")


def _normalize_digits(text: str) -> str:
    table = str.maketrans(_PERSIAN_DIGITS + _ARABIC_DIGITS, "0123456789" * 2)
    return text.translate(table)


def _digit_runs(text: str) -> set[str]:
    return set(_DIGITS_RE.findall(_normalize_digits(text)))


def _count_sentences(text: str) -> int:
    return len([s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()])


def _load_samples(count: int, seed: int, sids_file: Path | None) -> list[NewsPost]:
    posts = [NewsPost(**raw) for raw in json.loads(POSTS_PATH.read_text())]
    # فقط پست‌هایی که واقعاً به مدل می‌روند (بالای آستانهٔ متن کوتاه).
    long_enough = [p for p in posts if len(p.text.strip()) >= SHORT_TEXT_THRESHOLD]
    if sids_file is not None:
        # نمونهٔ فریزشده: news_posts.json هر ۱۵ دقیقه با اجرای تایمر رشد می‌کند،
        # پس نمونهٔ تصادفی بین دو اجرا جابه‌جا می‌شود و مقایسه بی‌جفت می‌ماند.
        wanted = json.loads(sids_file.read_text())
        by_sid = {p.sid: p for p in long_enough}
        return [by_sid[sid] for sid in wanted if sid in by_sid]
    random.Random(seed).shuffle(long_enough)
    return long_enough[:count]


def measure(
    count: int, runs: int, seed: int, sids_file: Path | None = None
) -> list[dict]:
    rows = []
    samples = _load_samples(count, seed, sids_file)
    for index, post in enumerate(samples, start=1):
        for run in range(1, runs + 1):
            row: dict = {
                "sid": post.sid,
                "run": run,
                "prompt_hash": PROMPT_HASH,
                "input_chars": len(post.text),
                "media_kind": post.media_kind.value if post.media_kind else None,
            }
            try:
                summary = summarize_single_post(post)
                in_digits = _digit_runs(post.text)
                kept = in_digits & _digit_runs(summary)
                row |= {
                    "summary_chars": len(summary),
                    "sentences": _count_sentences(summary),
                    "ratio": round(len(summary) / len(post.text), 3),
                    "input_digit_runs": len(in_digits),
                    "kept_digit_runs": len(kept),
                    "summary": summary,
                }
            except Exception as exc:  # noqa: BLE001 — خطای مدل باید در گزارش بماند
                row |= {"error": f"{type(exc).__name__}: {exc}"}
            rows.append(row)
            print(
                f"[{index}/{len(samples)} r{run}] "
                + (
                    row.get("error")
                    or f"{row['input_chars']}→{row['summary_chars']} chars, "
                    f"{row['sentences']} جمله، اعداد {row['kept_digit_runs']}/"
                    f"{row['input_digit_runs']}"
                ),
                flush=True,
            )
    return rows


def summarize_medians(rows: list[dict]) -> None:
    ok = [r for r in rows if "error" not in r]
    if not ok:
        print("هیچ خلاصهٔ سالمی ثبت نشد.")
        return
    for key in ("input_chars", "summary_chars", "sentences", "ratio"):
        print(f"میانهٔ {key}: {statistics.median(r[key] for r in ok)}")
    total_in = sum(r["input_digit_runs"] for r in ok)
    total_kept = sum(r["kept_digit_runs"] for r in ok)
    if total_in:
        print(f"اعداد حفظ‌شده: {total_kept}/{total_in} ({total_kept / total_in:.0%})")
    else:
        print("اعداد حفظ‌شده: در نمونه هیچ عددی نبود")
    print(f"اجرای ناموفق: {len(rows) - len(ok)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="مسیر فایل JSON خروجی")
    parser.add_argument("--n", type=int, default=16, help="تعداد پست نمونه")
    parser.add_argument("--runs", type=int, default=2, help="اجرا روی هر پست")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--sids",
        type=Path,
        default=None,
        help="فایل JSON حاوی فهرست sid — نمونهٔ فریزشده برای مقایسهٔ A/B",
    )
    parser.add_argument(
        "--save-sids",
        type=Path,
        default=None,
        help="ذخیرهٔ فهرست sid نمونهٔ انتخاب‌شده در این مسیر",
    )
    parser.add_argument(
        "--from-rows",
        type=Path,
        default=None,
        help="استخراج فهرست sid از فایل اندازه‌گیری قبلی (برای جفت‌کردن دو اجرا)",
    )
    args = parser.parse_args()

    if args.save_sids is not None:
        sids = [p.sid for p in _load_samples(args.n, args.seed, args.sids)]
        args.save_sids.parent.mkdir(parents=True, exist_ok=True)
        args.save_sids.write_text(json.dumps(sids, ensure_ascii=False, indent=2))
        print(f"فهرست نمونه نوشته شد: {args.save_sids} ({len(sids)} پست)")
        return

    if args.from_rows is not None:
        sids = list(dict.fromkeys(r["sid"] for r in json.loads(args.from_rows.read_text())))
        args.sids = args.from_rows.with_suffix(".sids.json")
        args.sids.write_text(json.dumps(sids, ensure_ascii=False, indent=2))
        print(f"فهرست sid از {args.from_rows} استخراج شد: {len(sids)} پست")

    rows = measure(args.n, args.runs, args.seed, args.sids)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"\nنوشته شد: {out}")
    summarize_medians(rows)


if __name__ == "__main__":
    main()
