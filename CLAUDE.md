# Bale News Digest

A bot that automatically fetches, judges the importance of, and summarizes news from a Bale messenger channel using an LLM.

## Main Flow

`main.py` → `news_collector.fetch_new_posts` (Bale public `POST https://api.ble.ir/api/v1/LoadHistory` for `ble.ir/s/<CHANNEL_SLUG>`) → `news_importance` (one LLM call: the importance that decides the send) → `news_summarizer` (summary + post link) → `bale_bot_message_sender` (send to target channel).

- There is no separate news classification: `judge_importance` is the only per-post LLM judgment and its verdict is what decides sending (a category layer existed until 2026-09-24; it cost an extra call for 76% of posts and the final decision rode on importance anyway). Output is one of `major`/`normal`/`trivial` (numeric scores measured as far less stable on the weak gateway); `MIN_IMPORTANCE` (env) is the send threshold. The prompt keeps `advertisement` always `trivial`, lets `sports`/`culture_art` be `major` only for a historic national achievement / the death of a national figure, and judges a multi-item digest by its most important item — all verified on 2026-09-24 over 112 unique real posts / 138 verdicts (raw verdicts in the untracked local `measurements/gate_v2*.json`). Evidence, honestly bounded: of 21 advertisement verdicts none came back `major`; of 34 posts the old pipeline sent, 29 stayed `major` and 5 were demoted to `normal` (single draw each on a round-robin gateway, so those 5 are a signal, not a median — one of them came back `major` on a later draw), and a demoted post is terminal because it is still persisted as seen. The shipped prompt was then spot-checked again on 8 real posts after the closing output-format line was added: 6/6 advertisements `trivial`, 2/2 previously-sent majors still `major`. A post whose judgment *failed* keeps `importance=None` and is **sent** (fail-open) — with no category veto left, that is the only leak channel, and it applies to every topic including advertisements; a content-free post (emoji/link only) is not that case: the collector records it as `trivial`, so it is dropped. Every judgment failure logs the raw model answer and `finish_reason` (added 2026-09-25, after a combo backend returned responses truncated at 4096 tokens with no usable label and the leak was undiagnosable after the fact): retries only help against a random bad answer, because the router is sticky per connection and all 4 attempts of a post hit the same backend — 9 of that day's 33 posts went to the channel unjudged within one 3-hour window.

- Already-seen posts are persisted in `news_posts.json` (keeps the last `MAX_STORED_POSTS`, default 5000). `sid` is exactly `f"{rid}-{date}"` as returned by the API (`rid` is a JSON string, may be a negative int64) — changing it would re-send every post.
- The channel's internal peer id comes from `PEER_ID` in `.env` and is never re-discovered at runtime; `scripts/resolve_peer_id.py` prints it once.
- Each post that passes the importance gate is summarized individually and dispatched immediately to the main channel (`BALE_BOT_CHAT_ID`) only — there are no per-category channels and no routing to decide.
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
- LLM prompts live as `IMPORTANCE_SYSTEM_PROMPT` in `news_importance.py` and `SYSTEM_PROMPT` in `news_summarizer.py`.
- The LLM is expected to return exactly one label or a structured summary; any prompt change must be verified against several real samples.
- File I/O errors in `utils.py` are logged, not raised — fall back to an empty list. Network/API calls in `news_collector.py` are the opposite: logged **and raised**, never swallowed into an empty list.
- The `LoadHistory` API is undocumented and returns a fixed page of 10 messages. Text for `documentMessage` lives at `message.documentMessage.caption.text` (the majority of this channel's posts) — reading only `textMessage` silently drops most news. Pagination anchor is `min(date) - 1`; the `-1` is mandatory.

## Workflow

- After completing any code change, commit and push it to the working branch. Do not leave changes uncommitted in the working tree.
