"""یک نمونهٔ ثابت از پست‌های واقعی را چند بار می‌سنجد و نتیجه را در JSON می‌نویسد.

برای مقایسهٔ قبل/بعد هر تغییر روی IMPORTANCE_SYSTEM_PROMPT: فهرست sidها را
می‌دهی، با پرامپت فعلی اجرا می‌کنی، پرامپت را عوض می‌کنی، دوباره اجرا می‌کنی و
دو فایل را کنار هم می‌گذاری. تعداد قرعه‌ها را کم نگه دار (روی گیت‌وی رایگان،
هر فراخوانی می‌تواند به مدل دیگری برسد).

    uv run python scripts/measure_importance_sample.py before.json slogan_before.json
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news_importance import IMPORTANCE_SYSTEM_PROMPT, judge_importance  # noqa: E402
from utils import load_posts  # noqa: E402


def run(sids: list[tuple[str, str]], runs: int, out_path: str) -> None:
    by_sid = {p.sid: p for p in load_posts()}
    rows = []

    for sid, label in sids:
        post = by_sid.get(sid)
        if post is None:
            print(f"⚠ sid پیدا نشد: {sid}")
            continue
        verdicts = []
        for _ in range(runs):
            try:
                verdicts.append(judge_importance(post.text).value)
            except Exception as e:
                verdicts.append(f"ERR:{type(e).__name__}")
        stored = post.importance.value if post.importance else "None"
        rows.append({"sid": sid, "label": label, "stored": stored, "verdicts": verdicts})
        print(f"  {label:42s} stored={stored:7s} -> {verdicts}")

    Path(out_path).write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    counts = Counter(v for r in rows for v in r["verdicts"])
    print(f"\n{out_path}: {len(rows)} posts × {runs} runs | {dict(counts)}")


if __name__ == "__main__":
    sids_path, out_path = sys.argv[1], sys.argv[2]
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    data = json.loads(Path(sids_path).read_text())
    print(f"prompt chars = {len(IMPORTANCE_SYSTEM_PROMPT)}")
    run([(d["sid"], d["label"]) for d in data], runs, out_path)
