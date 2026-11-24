"""Tiny raw Telegram Bot API client (no framework), so new fields like
icon_custom_emoji_id and button style work regardless of library version."""
import json
import logging
import re

import httpx

log = logging.getLogger("tg")


class TGError(Exception):
    pass


_EMOJI_RE = re.compile(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>', re.S)


def strip_emoji(text):
    return _EMOJI_RE.sub(r"\1", text) if text else text


def strip_markup(markup):
    if not markup:
        return markup
    rows = []
    for row in markup["inline_keyboard"]:
        new = []
        for b in row:
            b = dict(b)
            b.pop("icon_custom_emoji_id", None)
            b.pop("style", None)
            new.append(b)
        rows.append(new)
    return {"inline_keyboard": rows}


def _is_fancy_error(msg):
    msg = msg.lower()
    return any(k in msg for k in ("emoji", "button", "style", "entity", "entities"))


class TG:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}"
        self.http = httpx.AsyncClient(timeout=70)

    async def call(self, method, **params):
        params = {k: v for k, v in params.items() if v is not None}
        r = await self.http.post(f"{self.base}/{method}", json=params)
        data = r.json()
        if not data.get("ok"):
            raise TGError(f"{method}: {data.get('description')}")
        return data["result"]

    async def safe(self, method, **params):
        """Call; if Telegram rejects premium emoji / button styles, retry plain."""
        try:
            return await self.call(method, **params)
        except TGError as ex:
            if not _is_fancy_error(str(ex)):
                raise
            log.warning("Retrying without custom emoji/styles: %s", ex)
            for key in ("text", "caption"):
                if key in params:
                    params[key] = strip_emoji(params[key])
            if "reply_markup" in params:
                params["reply_markup"] = strip_markup(params["reply_markup"])
            return await self.call(method, **params)

    async def send_photo(self, chat_id, photo: bytes, caption, markup=None):
        async def _go(cap, mk):
            data = {"chat_id": str(chat_id), "caption": cap, "parse_mode": "HTML"}
            if mk:
                data["reply_markup"] = json.dumps(mk)
            r = await self.http.post(
                f"{self.base}/sendPhoto",
                data=data,
                files={"photo": ("card.png", photo, "image/png")},
            )
            res = r.json()
            if not res.get("ok"):
                raise TGError(f"sendPhoto: {res.get('description')}")
            return res["result"]

        try:
            return await _go(caption, markup)
        except TGError as ex:
            if not _is_fancy_error(str(ex)):
                raise
            return await _go(strip_emoji(caption), strip_markup(markup))
