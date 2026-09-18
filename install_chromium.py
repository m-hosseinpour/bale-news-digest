"""تهیهٔ یک Chromium محلی برای محیط‌هایی که دانلود مرورگر Playwright در آن‌ها بسته است.

Playwright باینری مرورگرش را از `cdn.playwright.dev` می‌گیرد که در برخی
مناطق (از جمله ایران) با خطای geo-block یعنی ۴۰۳ رد می‌شود. این اسکریپت
همان نسخهٔ Chromium را از registry پکیج‌های npm برمی‌دارد: پکیج
`@sparticuz/chromium` باینری را داخل خود tarball دارد، پس به هیچ CDN
بلاک‌شده‌ای نیاز نیست.

خروجی در `~/.cache/playwright-chromium/` می‌نشیند و `config.py` تا زمانی که
`CHROMIUM_EXECUTABLE_PATH` تنظیم نشده باشد، خودش همین مسیر پیش‌فرض را برمی‌دارد.
اگر این مرورگر موجود نباشد، Playwright به مرورگر بستهٔ خودش برمی‌گردد.

اجرا:
    uv run python install_chromium.py
    NPM_REGISTRY=https://registry.npmmirror.com uv run python install_chromium.py
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import brotli
import requests

PACKAGE = "@sparticuz/chromium"
# Chromium 153 — همان نسخهٔ سرشناسی که Playwright 1.63 انتظار دارد.
CHROMIUM_VERSION = "153.0.0"

DEFAULT_TARGET = Path.home() / ".cache" / "playwright-chromium"
DEFAULT_REGISTRY = "https://registry.npmjs.org"

# کتابخانه‌های همراه باینری (NSS، SwiftShader، فونت‌ها) که روی سرورهای مینیمال لازم می‌شوند.
LIB_ARCHIVES = ("al2023.tar.br", "swiftshader.tar.br", "fonts.tar.br")

DOWNLOAD_ATTEMPTS = 30
CHUNK_SIZE = 1 << 16


def _registry() -> str:
    return os.getenv("NPM_REGISTRY", DEFAULT_REGISTRY).rstrip("/")


def _tarball_url() -> str:
    return f"{_registry()}/{PACKAGE}/-/{PACKAGE.split('/')[-1]}-{CHROMIUM_VERSION}.tgz"


def _is_complete_tarball(path: Path) -> bool:
    """tarball ناقص (دانلود نصفه) هنگام پیمایش اعضا خطا می‌دهد."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with tarfile.open(path, "r:gz") as tar:
            for _ in tar:
                pass
            return "package/bin/chromium.br" in tar.getnames()
    except (tarfile.TarError, EOFError, OSError):
        return False


def _download(url: str, dest: Path) -> None:
    """دانلود resumable؛ اتصال به میرورها معمولاً ناپایدار است."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        if _is_complete_tarball(dest):
            print(f"✓ دانلود کامل شد ({dest.stat().st_size:,} بایت)")
            return

        offset = dest.stat().st_size if dest.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}

        try:
            with requests.get(url, headers=headers, stream=True, timeout=(15, 120)) as resp:
                if offset and resp.status_code != 206:
                    # سرور range را نادیده گرفت؛ از صفر شروع می‌کنیم.
                    offset = 0
                    dest.unlink(missing_ok=True)
                resp.raise_for_status()

                mode = "ab" if offset else "wb"
                with open(dest, mode) as fh:
                    for chunk in resp.iter_content(CHUNK_SIZE):
                        fh.write(chunk)
        except Exception as e:
            print(f"  تلاش {attempt}: {type(e).__name__}: {str(e)[:120]}")
            continue

        print(f"  تلاش {attempt}: {dest.stat().st_size:,} بایت")

    raise RuntimeError(
        f"دانلود از {url} بعد از {DOWNLOAD_ATTEMPTS} تلاش کامل نشد. "
        "می‌توانی با NPM_REGISTRY یک میرور دیگر بدهی."
    )


def _unpack(tarball: Path, target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tarball, "r:gz") as tar:
        chromium_br = tar.extractfile("package/bin/chromium.br")
        if chromium_br is None:
            raise RuntimeError("bin/chromium.br در tarball پیدا نشد.")
        binary = target / "chromium"
        binary.write_bytes(brotli.decompress(chromium_br.read()))
        binary.chmod(0o755)

        lib_dir = target / "lib"
        if lib_dir.exists():
            shutil.rmtree(lib_dir)
        lib_dir.mkdir()

        for name in LIB_ARCHIVES:
            member = tar.extractfile(f"package/bin/{name}")
            if member is None:
                continue
            with tarfile.open(fileobj=io.BytesIO(brotli.decompress(member.read()))) as libs:
                libs.extractall(lib_dir, filter="data")

    return binary


def _report_version(binary: Path) -> None:
    try:
        out = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, timeout=30
        )
        print(f"  نسخه: {out.stdout.strip() or out.stderr.strip()}")
    except Exception as e:
        print(f"  (اجرای --version ممکن نشد: {type(e).__name__})")


def main() -> int:
    target = Path(os.getenv("CHROMIUM_INSTALL_DIR", DEFAULT_TARGET))
    binary = target / "chromium"

    if binary.exists() and "--force" not in sys.argv:
        print(f"✓ Chromium از قبل موجود است: {binary}")
        _report_version(binary)
        print(f"\nCHROMIUM_EXECUTABLE_PATH={binary}")
        return 0

    url = _tarball_url()
    print(f"منبع: {url}")
    print(f"مقصد: {binary}\n")

    tarball = target / "chromium.tgz"
    _download(url, tarball)

    print("در حال باز کردن بسته...")
    binary = _unpack(tarball, target)
    tarball.unlink(missing_ok=True)

    print(f"✓ آماده شد ({binary.stat().st_size:,} بایت)")
    _report_version(binary)
    print(f"\nCHROMIUM_EXECUTABLE_PATH={binary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
