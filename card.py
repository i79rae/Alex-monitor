import asyncio
import io
from datetime import datetime, timezone

import httpx
from PIL import Image, ImageDraw, ImageFont

import config

W, H = 900, 500
BG = (9, 16, 14)
PANEL = (14, 28, 24)
GREEN = (46, 204, 113)
WHITE = (240, 245, 242)
MUTED = (130, 150, 142)


def _font(size, bold=True):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for p in (
        config.FONT_PATH,
        f"/usr/share/fonts/truetype/dejavu/{name}",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        if p:
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _short(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
    return f"{n:,}"


async def render_card(info) -> bytes:
    avatar = None
    if info.avatar_url:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(info.avatar_url)
                if r.status_code == 200:
                    avatar = r.content
        except Exception:
            pass
    return await asyncio.to_thread(_draw, info, avatar)


def _draw(info, avatar_bytes) -> bytes:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # soft green glow in the corner
    for i in range(12):
        d.ellipse((-200 + i * 12, -200 + i * 12, 420 - i * 12, 300 - i * 12),
                  fill=(9 + i, 16 + i * 3, 14 + i * 2))
    d.rounded_rectangle((24, 24, W - 24, H - 24), 28, outline=GREEN, width=2)

    d.text((60, 56), "ACCOUNT RADAR", font=_font(18), fill=GREEN)
    d.text((60, 150), (info.full_name or info.username)[:22], font=_font(54), fill=WHITE)
    d.text((60, 220), f"@{info.username}", font=_font(26, False), fill=MUTED)

    tags = []
    if info.verified:
        tags.append("VERIFIED")
    if info.private:
        tags.append("PRIVATE")
    if tags:
        d.text((60, 262), "  ·  ".join(tags), font=_font(18), fill=GREEN)

    # stats
    stats = [(_short(info.posts), "POSTS"), (_short(info.followers), "FOLLOWERS"),
             (_short(info.following), "FOLLOWING")]
    x = 60
    for value, label in stats:
        d.rounded_rectangle((x, 320, x + 230, 420), 18, fill=PANEL)
        d.text((x + 20, 332), value, font=_font(38), fill=WHITE)
        d.text((x + 20, 384), label, font=_font(15), fill=MUTED)
        x += 250

    # avatar
    size = 200
    cx, cy = W - 170, 190
    if avatar_bytes:
        try:
            av = Image.open(io.BytesIO(avatar_bytes)).convert("RGB").resize((size, size))
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
            d.ellipse((cx - size // 2 - 5, cy - size // 2 - 5, cx + size // 2 + 5, cy + size // 2 + 5),
                      outline=GREEN, width=4)
            img.paste(av, (cx - size // 2, cy - size // 2), mask)
        except Exception:
            avatar_bytes = None
    if not avatar_bytes:
        d.ellipse((cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2),
                  fill=PANEL, outline=GREEN, width=4)
        letter = (info.username[:1] or "?").upper()
        d.text((cx - 24, cy - 40), letter, font=_font(80), fill=GREEN)

    ts = datetime.now(timezone.utc).strftime("%d %b %Y · %H:%M:%S UTC")
    d.text((60, H - 62), ts, font=_font(16, False), fill=MUTED)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
