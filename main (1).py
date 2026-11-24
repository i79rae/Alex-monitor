import asyncio
import logging
import os
import re
import time
from collections import defaultdict

import config
import db
import ui
from card import render_card
from checker import Checker
from tg import TG

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

START = time.time()
tg = TG(config.BOT_TOKEN)
checker = Checker(config.PROXIES)
pending = {}  # user_id -> mode waiting for a username
ME = {"username": ""}
_tasks = set()


# ---------------- helpers ----------------
def parse_username(text):
    text = (text or "").strip()
    if not text:
        return None
    t = text.split()[0]
    t = re.sub(r"^(https?://)?(www\.)?instagram\.com/", "", t, flags=re.I)
    t = t.split("?")[0].strip("/").lstrip("@")
    return t.lower() if re.fullmatch(r"[A-Za-z0-9._]{1,30}", t) else None


async def say(chat_id, text, markup=None):
    return await tg.safe(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=markup,
        link_preview_options={"is_disabled": True},
    )


async def send_home(chat_id, first_name):
    text = ui.home_text(first_name, time.time() - START, await db.count_radars())
    await say(chat_id, text, ui.home_kb())


# ---------------- actions ----------------
async def do_scan(chat_id, username):
    await say(chat_id, f"{ui.e('alert')} <b>radar sweeping</b> @{username}")
    info = await checker.check(username)
    if info.status == "error":
        await say(chat_id, ui.T_ERROR, ui.kb([ui.btn("Retry", "rescan", cb=f"scan:{username}")]))
        return
    await db.set_target_if_changed(username, info.status)

    if info.status == "not_found":
        await say(chat_id, ui.down_text(username), ui.down_kb(username))
        return

    caption = ui.live_caption(info, ME["username"])
    markup = ui.live_kb(username, ME["username"])
    photo = None
    try:
        photo = await render_card(info)
    except Exception:
        log.exception("card render failed")
    if photo:
        await tg.send_photo(chat_id, photo, caption, markup)
    else:
        await say(chat_id, caption, markup)


async def do_track(chat_id, uid, mode, username):
    if await db.count_radars(uid) >= config.MAX_RADARS:
        await say(chat_id, f"{ui.e('alert')} Radar limit reached ({config.MAX_RADARS}). Stop one first.",
                  ui.kb(ui.home_row()))
        return
    info = await checker.check(username)
    if info.status == "error":
        await say(chat_id, ui.T_ERROR, ui.kb(ui.home_row()))
        return
    await db.set_target_if_changed(username, info.status)

    problem = None
    if mode == "ban" and info.status != "live":
        problem = f"@{username} is already down. Use <b>Unban Radar</b> instead."
    elif mode == "unban" and info.status == "live":
        problem = f"@{username} is already live. Use <b>Ban Radar</b> instead."
    elif mode in ("tick", "post") and info.status != "live":
        problem = f"@{username} isn't live, so there's nothing to watch."
    if problem:
        await say(chat_id, f"{ui.e('alert')} {problem}", ui.kb(ui.home_row()))
        return

    baseline = ""
    if mode == "tick":
        baseline = "1" if info.verified else "0"
    elif mode == "post":
        baseline = str(info.posts)

    is_new = await db.add_radar(uid, username, mode, baseline)
    await say(chat_id, ui.tracking_text(mode, username, is_new), ui.tracking_kb(username, mode))


async def show_my(chat_id, uid, mode):
    radars = await db.user_radars(uid, mode)
    title = f"{ui.e('list')} <b>My {ui.MODES[mode]}s</b>"
    if not radars:
        await say(chat_id, f"{title}\n\nNone running. Start one from the menu.", ui.kb(ui.home_row()))
        return
    lines = "\n".join(f"├ @{r['username']}" for r in radars[:-1])
    lines += ("\n" if lines else "") + f"└ @{radars[-1]['username']}"
    await say(chat_id, f"{title}\n\n{lines}\n\nTap one to stop it.", ui.list_kb(radars, mode))


async def show_insights(chat_id, uid):
    mine = await db.user_radars(uid)
    counts = defaultdict(int)
    for r in mine:
        counts[r["mode"]] += 1
    text = (
        f"{ui.e('insights')} <b>Insights</b>\n\n"
        f"├ Your radars · {len(mine)}\n"
        f"├ Unban · {counts['unban']}  Ban · {counts['ban']}\n"
        f"├ Tick · {counts['tick']}  Post · {counts['post']}\n"
        f"├ Total users · {await db.count_users()}\n"
        f"└ Uptime · {ui.fmt_dur(time.time() - START)}"
    )
    await say(chat_id, text, ui.kb(ui.home_row()))


# ---------------- update handlers ----------------
async def on_message(msg):
    if msg["chat"]["type"] != "private":
        return
    chat_id = msg["chat"]["id"]
    uid = msg["from"]["id"]
    first = msg["from"].get("first_name", "there")
    text = msg.get("text") or ""
    await db.add_user(uid)

    # Premium emoji ID finder: send any premium emoji and the bot replies with its ID
    ents = [x for x in msg.get("entities", []) if x["type"] == "custom_emoji"]
    if ents:
        raw = text.encode("utf-16-le")
        lines = []
        for x in ents:
            ch = raw[2 * x["offset"]: 2 * (x["offset"] + x["length"])].decode("utf-16-le")
            lines.append(f"{ch}  <code>{x['custom_emoji_id']}</code>")
        await say(chat_id, "<b>Custom emoji IDs</b>\n" + "\n".join(lines) +
                  "\n\nPaste these into <code>emojis.json</code>.")
        return

    cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
    if cmd in ("/start", "/menu"):
        pending.pop(uid, None)
        await send_home(chat_id, first)
    elif cmd == "/help":
        await say(chat_id, ui.GUIDE, ui.kb(ui.home_row()))
    elif cmd == "/cancel":
        pending.pop(uid, None)
        await send_home(chat_id, first)
    elif cmd == "/emojiid":
        await say(chat_id, "Send me a Premium custom emoji and I'll reply with its ID.")
    elif cmd:
        await send_home(chat_id, first)
    else:
        username = parse_username(text)
        if not username:
            await say(chat_id, f"{ui.e('alert')} That doesn't look like a username. Try <code>@name</code>.",
                      ui.cancel_kb())
            return
        mode = pending.pop(uid, "scan")
        if mode == "scan":
            await do_scan(chat_id, username)
        else:
            await do_track(chat_id, uid, mode, username)


async def on_callback(cq):
    await tg.safe("answerCallbackQuery", callback_query_id=cq["id"])
    msg = cq.get("message")
    if not msg:
        return
    chat_id = msg["chat"]["id"]
    uid = cq["from"]["id"]
    first = cq["from"].get("first_name", "there")
    parts = cq["data"].split(":")
    action = parts[0]

    if action == "home":
        pending.pop(uid, None)
        await send_home(chat_id, first)
    elif action == "cancel":
        pending.pop(uid, None)
        await send_home(chat_id, first)
    elif action == "ask":
        mode = parts[1]
        pending[uid] = mode
        await say(chat_id, ui.ask_text(mode, ME["username"]), ui.cancel_kb())
    elif action == "scan":
        await do_scan(chat_id, parts[1])
    elif action == "track":
        await do_track(chat_id, uid, parts[1], parts[2])
    elif action == "stop":
        mode, username = parts[1], parts[2]
        ok = await db.remove_user_radar(uid, username, mode)
        await say(chat_id,
                  f"{ui.e('stop')} {ui.MODES[mode]} stopped for @{username}." if ok
                  else "That radar wasn't running.",
                  ui.kb(ui.home_row()))
    elif action == "my":
        await show_my(chat_id, uid, parts[1])
    elif action == "insights":
        await show_insights(chat_id, uid)
    elif action == "guide":
        await say(chat_id, ui.GUIDE, ui.kb(ui.home_row()))


async def dispatch(update):
    try:
        if "message" in update:
            await on_message(update["message"])
        elif "callback_query" in update:
            await on_callback(update["callback_query"])
    except Exception:
        log.exception("handler failed")


# ---------------- radar loop ----------------
async def notify(r, text, markup):
    try:
        await say(r["user_id"], text, markup)
    except Exception:
        log.exception("notify failed for %s", r["user_id"])


async def handle_radar(r, info, prev, now):
    mode, username = r["mode"], r["username"]

    if mode == "ban" and info.status == "not_found":
        await notify(r, ui.banned_text(username), ui.banned_kb(username))
        await db.remove_radar(r["id"])

    elif mode == "unban" and info.status == "live":
        since = prev["since"] if prev and prev["status"] == "not_found" else r["created"]
        await notify(r, ui.recovered_text(info, now - since), ui.recovered_kb(username))
        await db.remove_radar(r["id"])

    elif mode == "tick" and info.status == "live":
        if ("1" if info.verified else "0") != r["baseline"]:
            await notify(r, ui.tick_text(info), ui.result_kb(username))
            await db.remove_radar(r["id"])

    elif mode == "post" and info.status == "live":
        old = int(r["baseline"] or 0)
        if info.posts != old:
            await notify(r, ui.post_text(info, old, info.posts), ui.result_kb(username))
            await db.set_baseline(r["id"], str(info.posts))  # keeps running


async def radar_loop():
    log.info("radar loop started (every %ss)", config.SCAN_INTERVAL)
    while True:
        t0 = time.time()
        try:
            by_user = defaultdict(list)
            for r in await db.all_radars():
                by_user[r["username"]].append(r)

            sem = asyncio.Semaphore(config.CONCURRENCY)

            async def work(username, rs):
                async with sem:
                    info = await checker.check(username)
                if info.status == "error":
                    return  # transient; keep previous state
                prev = await db.get_target(username)
                now = int(time.time())
                if prev is None or prev["status"] != info.status:
                    await db.set_target(username, info.status)
                for r in rs:
                    await handle_radar(r, info, prev, now)

            await asyncio.gather(*(work(u, rs) for u, rs in by_user.items()),
                                 return_exceptions=True)
        except Exception:
            log.exception("radar loop error")
        await asyncio.sleep(max(1, config.SCAN_INTERVAL - (time.time() - t0)))


# ---------------- main ----------------
async def health(reader, writer):
    try:
        await reader.read(1024)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
        await writer.drain()
    finally:
        writer.close()


async def start_health():
    port = int(os.getenv("PORT", "10000"))
    await asyncio.start_server(health, "0.0.0.0", port)


async def main():
    if not config.BOT_TOKEN:
        raise SystemExit("Set BOT_TOKEN in .env first.")
    ui.load_emoji_ids()
    await db.init()
    me = await tg.call("getMe")
    ME["username"] = me["username"]
    await tg.call("setMyCommands", commands=[
        {"command": "start", "description": "Open the menu"},
        {"command": "help", "description": "How it works"},
        {"command": "cancel", "description": "Cancel current action"},
        {"command": "emojiid", "description": "Get a Premium emoji ID"},
    ])
    log.info("Running as @%s", ME["username"])
    await start_health()
    asyncio.create_task(radar_loop())

    offset = None
    while True:
        try:
            updates = await tg.call("getUpdates", offset=offset, timeout=50,
                                    allowed_updates=["message", "callback_query"])
        except Exception as ex:
            log.warning("getUpdates failed: %s", ex)
            await asyncio.sleep(3)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            t = asyncio.create_task(dispatch(u))
            _tasks.add(t)
            t.add_done_callback(_tasks.discard)


if __name__ == "__main__":
    asyncio.run(main())
