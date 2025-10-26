# Organic Search Bot (VK + Telegram via Telemetr, optional TGStat)

## Quick start
1. Create `.env` from `.env.example` and fill variables.
2. Deploy / run: `python -m bot.main` (Procfile uses this).
3. In Telegram, send `/organic` to run an organic search workflow.

## Environment (.env)
- `BOT_TOKEN` — Telegram bot token
- VK:
  - `VK_TOKEN` — VK API access token
  - `VK_MIN_VIEWS` — default 500
  - `VK_MAX_PAGES` — default 5 (pages * 200 posts)
  - `VK_FUZZY_THRESHOLD` — default 0.62
- Telemetr:
  - `TELEMETR_TOKEN` — Bearer token
  - `USE_TELEMETR` — 1/0 (default 1)
  - `TELEMETR_STRICT` — 1 = exact phrase (default), 0 = fuzzy
  - `TELEMETR_PAGES` — default 5
  - `TELEMETR_FUZZY_THRESHOLD` — default 0.70
- TGStat (optional fallback):
  - `USE_TGSTAT` — 1/0 (default 0)
  - `TGSTAT_TOKEN` — API token

## Commands
- `/start` `/help` — basic help
- `/organic` — ask for a date range and then a list of phrases (one per line).

## Notes
- Telegram search uses Telemetr (`/channels/posts/search`) with strict phrase match by default.
- VK search uses `newsfeed.search` with fuzzy scoring + `views >= VK_MIN_VIEWS` (500 by default).
- Diagnostics are returned to chat with details if enabled by logic.
