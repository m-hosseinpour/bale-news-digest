# Bale News Digest

A bot that automatically fetches, classifies, and summarizes news from a Bale messenger channel using an LLM.

## Main Flow

`main.py` → `NewsCollector` (Selenium/Firefox on `ble.ir/akharinkhabar`) → `news_classifier` (LLM classification) → `news_summarizer` (summary + post link) → `bale_bot_message_sender` (send to target channel).

- Already-seen posts are persisted in `news_posts.json` (keeps the last 1000 items).
- Each "important" post (those in `IMPORTANT_CATEGORIES`) is summarized individually and dispatched immediately to the main channel and, if configured, to its category's dedicated channel (`BALE_BOT_CHAT_ID_<CATEGORY>`).
- `bot_webhook.py` returns a fixed reply for the bot's private messages (HTTPS required).

## File Layout

| File | Role |
|---|---|
| `main.py` | Entry point; one full run: collect → classify → summarize → send. |
| `config.py` | Loads `.env`; defines `IMPORTANT_CATEGORIES`, `CHANNEL_URL`, Selenium settings. |
| `model.py` | `NewsCategory` (enum) and `NewsPost` (pydantic). |
| `news_collector.py` | Scrolls the channel with headless Firefox; extracts post text. |
| `news_classifier.py` | Prompt + LLM call for classification. |
| `news_summarizer.py` | Prompt + LLM call for Persian summarization. |
| `bot_webhook.py` | Flask webhook returning a fixed reply to private messages. |
| `bale_bot_message_sender.py` | Sends messages to a Bale channel/chat. |
| `set_webhook.py` | Registers the webhook URL on the Bale bot. |
| `open_ai_client_provider.py` | OpenAI-compatible client (default: local Ollama). |

## Requirements

- Python 3.11+, `uv`
- Firefox + geckodriver (`sudo apt install firefox firefox-geckodriver`)
- OpenAI-compatible LLM (default: Ollama on `localhost:11434`)

## Common Commands

```shell
uv sync
cp .env.example .env        # then set BALE_BOT_TOKEN, BALE_BOT_CHAT_ID, OPEN_AI_API_KEY
uv run python main.py                                # one collect/summarize run
uv run flask --app bot_webhook run --port 8001        # webhook (dev)
uv run gunicorn --bind 127.0.0.1:8001 bot_webhook:app  # webhook (prod)
uv run python set_webhook.py                         # register the webhook
```

## Key `.env` Variables

- `BALE_BOT_TOKEN`, `BALE_BOT_CHAT_ID` — destination for summaries
- `OPEN_AI_BASE_URL`, `OPEN_AI_MODEL_NAME`, `OPEN_AI_API_KEY` — LLM config
- `CHANNEL_URL` — source channel (default: `https://ble.ir/s/akharinkhabar`)
- `BALE_BOT_CHAT_ID_<CATEGORY>` — optional dedicated channel per important category (e.g. `BALE_BOT_CHAT_ID_WAR_CONFLICT`)
- `MAX_SCROLLS`, `MAX_DRIVER_REUSE`, `PAGE_LOAD_TIMEOUT` — Selenium resource controls
- `HEADLESS`, `DISABLE_IMAGES` — memory optimizations for VPS
- `PUBLIC_WEBHOOK_URL` — used by `set_webhook.py`

## Code Style Notes

- Type hints throughout; pydantic v2 for models and validation.
- LLM prompts live as `SYSTEM_PROMPT` constants in `news_classifier.py` and `news_summarizer.py`.
- The LLM is expected to return exactly one label or a structured summary; any prompt change must be verified against several real samples.
- File I/O errors in `utils.py` are logged, not raised — fall back to an empty list.
- `MAX_DRIVER_REUSE=0` disables the automatic Firefox restart.

## CI/CD

- `.github/workflows/deploy.yml` — GitHub Action for deployment.
