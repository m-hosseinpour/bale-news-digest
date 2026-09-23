# Bale News Digest

A bot that automatically fetches, classifies, and summarizes news from a Bale messenger channel using an LLM.

## Main Flow

`main.py` → `news_collector.fetch_new_posts` (Bale public `POST https://api.ble.ir/api/v1/LoadHistory` for `ble.ir/s/<CHANNEL_SLUG>`) → `news_classifier` (LLM classification) → `news_summarizer` (summary + post link) → `bale_bot_message_sender` (send to target channel).

- Already-seen posts are persisted in `news_posts.json` (keeps the last 1000 items). `sid` is exactly `f"{rid}-{date}"` as returned by the API (`rid` is a JSON string, may be a negative int64) — changing it would re-send every post.
- The channel's internal peer id comes from `PEER_ID` in `.env` and is never re-discovered at runtime; `scripts/resolve_peer_id.py` prints it once.
- Each "important" post (those in `IMPORTANT_CATEGORIES`) is summarized individually and dispatched immediately to the main channel and, if configured, to its category's dedicated channel (`BALE_BOT_CHAT_ID_<CATEGORY>` env var).
- If the post carries an attachment, it is sent with the summary via `sendPhoto`/`sendVideo`/`sendAudio`/`sendDocument` using the `documentMessage.url` — Bale downloads it server-side, so nothing is uploaded by us. Media has no `file_id` (LoadHistory doesn't return one) and `copyMessage`/`forwardMessage` is impossible (bot has no access to the source channel).
- Message text is sent as plain text; only the last line is a markdown link `[لینک خبر مرجع](url)`. No `parse_mode` is set.

## Common Commands

```shell
uv sync
uv run python main.py                                # one collect/summarize run
uv run pytest                                         # unit tests (no network)
uv run python scripts/resolve_peer_id.py akharinkhabar # print the channel's PEER_ID
uv run python scripts/verify_collector.py             # message-kind / dedup sanity check
uv run flask --app bot_webhook run --port 8001        # webhook (dev)
uv run gunicorn --bind 127.0.0.1:8001 bot_webhook:app  # webhook (prod)
uv run python set_webhook.py                         # register the webhook
```

## Code Style Notes

- Type hints throughout; pydantic v2 for models and validation.
- LLM prompts live as `SYSTEM_PROMPT` constants in `news_classifier.py` and `news_summarizer.py`.
- The LLM is expected to return exactly one label or a structured summary; any prompt change must be verified against several real samples.
- File I/O errors in `utils.py` are logged, not raised — fall back to an empty list. Network/API calls in `news_collector.py` are the opposite: logged **and raised**, never swallowed into an empty list.
- The `LoadHistory` API is undocumented and returns a fixed page of 10 messages. Text for `documentMessage` lives at `message.documentMessage.caption.text` (the majority of this channel's posts) — reading only `textMessage` silently drops most news. Pagination anchor is `min(date) - 1`; the `-1` is mandatory.

## Workflow

- After completing any code change, commit and push it to the working branch. Do not leave changes uncommitted in the working tree.
