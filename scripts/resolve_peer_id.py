"""یک‌بار اجرا کن تا آیدی داخلی کانال را بگیری و در .env بگذاری.

    uv run python scripts/resolve_peer_id.py akharinkhabar
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news_collector import resolve_peer_id  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("طرز استفاده: uv run python scripts/resolve_peer_id.py <channel_slug>")
        print("مثال: uv run python scripts/resolve_peer_id.py akharinkhabar")
        return 2

    peer_id = resolve_peer_id(sys.argv[1])
    print(f"\nاین خط را در .env بگذار:\nPEER_ID={peer_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
