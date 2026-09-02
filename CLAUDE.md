# Bale News Digest

A bot that automatically fetches, classifies, and summarizes news from a Bale messenger channel using an LLM.

## Main Flow

`main.py` → `NewsCollector` (Selenium/Firefox on `ble.ir/akharinkhabar`) → `news_classifier` (LLM classification) → `news_summarizer` (summary + post link) → `bale_bot_message_sender` (send to target channel).

- Already-seen posts are persisted in `news_posts.json` (keeps the last 1000 items).
- Each "important" post (those in `IMPORTANT_CATEGORIES`) is summarized individually and dispatched immediately to the main channel and, if configured, to its category's dedicated channel (`BALE_BOT_CHAT_ID_<CATEGORY>` env var).

## Common Commands

```shell
uv sync
uv run python main.py                                # one collect/summarize run
uv run flask --app bot_webhook run --port 8001        # webhook (dev)
uv run gunicorn --bind 127.0.0.1:8001 bot_webhook:app  # webhook (prod)
uv run python set_webhook.py                         # register the webhook
```

## Code Style Notes

- Type hints throughout; pydantic v2 for models and validation.
- LLM prompts live as `SYSTEM_PROMPT` constants in `news_classifier.py` and `news_summarizer.py`.
- The LLM is expected to return exactly one label or a structured summary; any prompt change must be verified against several real samples.
- File I/O errors in `utils.py` are logged, not raised — fall back to an empty list.
- `MAX_DRIVER_REUSE=0` disables the automatic Firefox restart.

## Workflow

- After completing any code change, commit and push it to the working branch. Do not leave changes uncommitted in the working tree.
