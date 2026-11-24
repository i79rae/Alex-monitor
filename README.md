# Instagram Radar Bot (Telegram)

Scan accounts, get alerts when they're banned / unbanned, verified-badge changes, and post-count changes.
Supports **Telegram Premium custom emojis** in messages and as button icons.

## Setup
1. Create a bot with @BotFather, copy the token.
2. `cp .env.example .env` and paste `BOT_TOKEN`.
3. `pip install -r requirements.txt`
4. `python main.py`

## Premium emojis
Messages and buttons use Telegram custom emojis once you give the bot their IDs.
1. Run the bot and send any Premium emoji to it. It replies with the ID.
2. Paste the IDs into `emojis.json` (keys: star, live, banned, alert, bell, scan, unban, ban...).
3. Restart. Empty IDs fall back to normal emojis, so nothing breaks.

Telegram only allows bots to use custom emojis in private chats when the **bot owner has Premium**
(or the bot owns a Fragment username). Use the same account that created the bot in @BotFather.
Coloured buttons (blue/green/red) use the newer button `style` field; if Telegram rejects it,
the bot automatically retries with plain buttons.

## How it works
- `checker.py` fetches public profile data. 404 or empty = not found (banned/deactivated).
- `main.py` radar loop: every `SCAN_INTERVAL` seconds, checks each distinct watched username once
  and notifies all watchers when the state flips.
- Radar types: ban, unban, tick, post.

## Important
- Instagram rate-limits and blocks scraping, and automated checking may break their terms.
  Add `PROXIES` in `.env` for rotation, keep intervals reasonable, or replace `Checker` with a
  paid data API (keep the same `Profile` return shape).
- "Not found" can't distinguish ban from deletion or a username change.
