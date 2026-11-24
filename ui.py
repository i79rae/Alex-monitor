"""All texts, keyboards and Premium-emoji helpers."""
import html
import json
from pathlib import Path
from urllib.parse import quote

import config

# name -> normal emoji used when you haven't set a Premium emoji ID
FALLBACK = {
    "star": "🚀", "live": "🟢", "banned": "🔴", "alert": "‼️", "bell": "🔔",
    "hourglass": "⏳", "bolt": "⚡", "radar": "📡", "scan": "🔍", "unban": "✅",
    "ban": "🚫", "tick": "☑️", "post": "📮", "list": "📋", "insights": "⚙️",
    "guide": "📖", "support": "💬", "home": "🏠", "view": "📷", "rescan": "🔄",
    "share": "📤", "stop": "⏹", "cancel": "✖️",
}

_ids = {}


def load_emoji_ids():
    """Reads emojis.json. Call again to hot-reload."""
    global _ids
    path = Path(__file__).with_name("emojis.json")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        _ids = {k: str(v) for k, v in raw.items() if v and not k.startswith("_")}
    except Exception:
        _ids = {}


def e(name):
    """Emoji for use inside message text (HTML parse mode)."""
    fb = FALLBACK[name]
    cid = _ids.get(name)
    return f'<tg-emoji emoji-id="{cid}">{fb}</tg-emoji>' if cid else fb


def btn(label, name=None, cb=None, url=None, style=None):
    """Inline button. Premium emoji shows as the button icon when an ID is set."""
    b = {}
    cid = _ids.get(name) if name else None
    if cid:
        b["icon_custom_emoji_id"] = cid
        b["text"] = label
    else:
        b["text"] = f"{FALLBACK[name]} {label}" if name else label
    if cb:
        b["callback_data"] = cb
    if url:
        b["url"] = url
    if style:  # "primary" (blue) | "success" (green) | "danger" (red)
        b["style"] = style
    return b


def kb(*rows):
    return {"inline_keyboard": [list(r) for r in rows]}


# ---------- formatting ----------
def fmt_num(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
    return f"{n:,}"


def fmt_dur(seconds):
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {sec}s"
    if m:
        return f"{m}m {sec}s"
    return f"{sec}s"


def esc(s):
    return html.escape(s or "")


MODES = {
    "scan": "Scan an Account",
    "ban": "Ban Radar",
    "unban": "Unban Radar",
    "tick": "Tick Radar",
    "post": "Post Radar",
}

MODE_HELP = {
    "ban": "alerts you the moment the account goes down",
    "unban": "alerts you the moment a banned account comes back",
    "tick": "alerts you when the verified badge appears or disappears",
    "post": "alerts you when the post count changes",
}


# ---------- texts ----------
def home_text(first_name, uptime, radars):
    return (
        f"{e('star')} <b>{esc(config.BOT_NAME)}</b>\n"
        f"<i>Instagram Radar — bans, unbans, ticks &amp; new posts, live.</i>\n\n"
        f"Hey {esc(first_name)}, good to see you.\n\n"
        f"{e('alert')} <u>Radar status</u>\n"
        f"├ Status · online\n"
        f"├ Uptime · {fmt_dur(uptime)}\n"
        f"├ Radars running · {radars}\n"
        f"└ Scan rate · every {config.SCAN_INTERVAL}s\n\n"
        f"Pick a tool below ↓"
    )


def ask_text(mode, bot_username):
    return (
        f"{e('scan')} <b>{MODES[mode]}</b>\n"
        f"<i>@{esc(bot_username)} · Instagram Radar</i>\n\n"
        f"├ Send a username to {'scan' if mode == 'scan' else 'watch'}\n"
        f"└ <code>username</code> · <code>@username</code> · instagram.com/name"
    )


def live_caption(info, bot_username):
    return (
        f"{e('live')} <b>Account is Live</b> — @{esc(info.username)}\n"
        f"└ {fmt_num(info.posts)} posts · {fmt_num(info.followers)} followers · "
        f"{fmt_num(info.following)} following\n\n"
        f"{e('bolt')} @{esc(bot_username)}"
    )


def down_text(username):
    return (
        f"{e('banned')} <b>Account Not Found</b> — @{esc(username)}\n"
        f"├ Banned, deactivated, or never existed\n"
        f"└ Track it with Unban Radar to know when it's back"
    )


def tracking_text(mode, username, is_new=True):
    head = f"{MODES[mode]} On" if is_new else f"{MODES[mode]} already running"
    return (
        f"{e('radar')} <b>{head}</b> — @{esc(username)}\n\n"
        f"{e('alert')} Radar on · sweeping every {config.SCAN_INTERVAL}s\n"
        f"{e('bell')} It {MODE_HELP[mode]}"
    )


def banned_text(username, info=None):
    return (
        f"{e('banned')} <b>Account Banned</b> — @{esc(username)}\n"
        f"├ It just disappeared from Instagram\n"
        f"└ Track Unban to be told when it returns"
    )


def recovered_text(info, tat):
    return (
        f"{e('unban')} <b>Account Recovered</b> — @{esc(info.username)}\n\n"
        f"{e('alert')} You're back on Instagram!\n"
        f"{e('hourglass')} Unban TAT: {fmt_dur(tat)}\n"
        f"└ {fmt_num(info.posts)} posts · {fmt_num(info.followers)} followers · "
        f"{fmt_num(info.following)} following"
    )


def tick_text(info):
    if info.verified:
        return f"{e('tick')} <b>Tick gained</b> — @{esc(info.username)} is now verified!"
    return f"{e('tick')} <b>Tick lost</b> — @{esc(info.username)} is no longer verified."


def post_text(info, old, new):
    if new > old:
        msg = f"+{new - old} new post{'s' if new - old > 1 else ''}"
    else:
        msg = f"{old - new} post{'s' if old - new > 1 else ''} removed"
    return (
        f"{e('post')} <b>Post activity</b> — @{esc(info.username)}\n"
        f"└ {msg} ({old} → {new})"
    )


T_ERROR = (
    f"{FALLBACK['alert']} <b>Couldn't reach Instagram right now.</b>\n"
    "It may be rate-limiting. Try again in a moment."
)

GUIDE = (
    f"{FALLBACK['guide']} <b>Guide</b>\n\n"
    "<b>Scan</b> — check if an account is live, with a stats card.\n"
    "<b>Ban Radar</b> — watch a live account; get pinged when it's banned.\n"
    "<b>Unban Radar</b> — watch a banned account; get pinged when it's back.\n"
    "<b>Tick Radar</b> — verified badge gained or lost.\n"
    "<b>Post Radar</b> — post count changes.\n\n"
    "Just send a username any time to scan it."
)


# ---------- keyboards ----------
def home_kb():
    rows = [
        [btn("Scan an Account", "scan", cb="ask:scan", style="primary")],
        [btn("Unban Radar", "unban", cb="ask:unban", style="success"),
         btn("Ban Radar", "ban", cb="ask:ban", style="danger")],
        [btn("Tick Radar", "tick", cb="ask:tick"), btn("Post Radar", "post", cb="ask:post")],
        [btn("My Unban Radars", "list", cb="my:unban"), btn("My Ban Radars", "list", cb="my:ban")],
        [btn("My Tick Radars", "list", cb="my:tick"), btn("My Post Radars", "list", cb="my:post")],
        [btn("Insights", "insights", cb="insights"), btn("Guide", "guide", cb="guide")],
    ]
    if config.SUPPORT_URL:
        rows.append([btn("Support", "support", url=config.SUPPORT_URL)])
    return kb(*rows)


def cancel_kb():
    return kb([btn("Cancel", "cancel", cb="cancel", style="danger")])


def home_row():
    return [btn("Home", "home", cb="home")]


def live_kb(username, bot_username):
    share = (
        "https://t.me/share/url?url="
        + quote(f"https://t.me/{bot_username}")
        + "&text="
        + quote(f"Check @{username} on Instagram radar")
    )
    return kb(
        [btn("View on Instagram", "view", url=f"https://instagram.com/{username}", style="primary")],
        [btn("Track Unban", "unban", cb=f"track:unban:{username}", style="success"),
         btn("Track Ban", "ban", cb=f"track:ban:{username}", style="danger")],
        [btn("Rescan", "rescan", cb=f"scan:{username}"), btn("Share", "share", url=share)],
        home_row(),
    )


def down_kb(username):
    return kb(
        [btn("Track Unban", "unban", cb=f"track:unban:{username}", style="success")],
        [btn("Rescan", "rescan", cb=f"scan:{username}")],
        home_row(),
    )


def tracking_kb(username, mode):
    return kb(
        [btn("View on Instagram", "view", url=f"https://instagram.com/{username}", style="primary")],
        [btn("Stop Radar", "stop", cb=f"stop:{mode}:{username}", style="danger"),
         btn("Rescan", "rescan", cb=f"scan:{username}")],
        [btn("My Unban Radars", "list", cb="my:unban"), btn("My Ban Radars", "list", cb="my:ban")],
        home_row(),
    )


def result_kb(username):
    return kb(
        [btn("View on Instagram", "view", url=f"https://instagram.com/{username}", style="primary")],
        [btn("Track Ban", "ban", cb=f"track:ban:{username}", style="danger"),
         btn("Rescan", "rescan", cb=f"scan:{username}")],
        home_row(),
    )


def recovered_kb(username):
    return kb(
        [btn("View on Instagram", "view", url=f"https://instagram.com/{username}", style="primary")],
        [btn("Track Ban", "ban", cb=f"track:ban:{username}", style="danger"),
         btn("Rescan", "rescan", cb=f"scan:{username}")],
        home_row(),
    )


def banned_kb(username):
    return kb(
        [btn("Track Unban", "unban", cb=f"track:unban:{username}", style="success")],
        [btn("Rescan", "rescan", cb=f"scan:{username}")],
        home_row(),
    )


def list_kb(radars, mode):
    rows, row = [], []
    for r in radars:
        row.append(btn(f"@{r['username']}", "stop", cb=f"stop:{mode}:{r['username']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(home_row())
    return kb(*rows)
