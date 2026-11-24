"""Instagram public-profile checker.

Uses Instagram's public web_profile_info endpoint. Instagram rate-limits and
changes this often, so: use PROXIES, keep SCAN_INTERVAL sane, and swap this
class for a paid data API if you need reliability. Keep the Profile shape and
the rest of the bot won't care.
"""
import html as htmlmod
import logging
import re
from dataclasses import dataclass

import httpx

log = logging.getLogger("checker")

URL = "https://www.instagram.com/api/v1/users/web_profile_info/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
    ),
    "x-ig-app-id": "936619743392459",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.instagram.com/",
}


def _num(s):
    s = s.replace(",", "").strip().upper()
    mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(s[-1:], 1)
    if mult != 1:
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


@dataclass
class Profile:
    username: str
    status: str  # "live" | "not_found" | "error"
    full_name: str = ""
    followers: int = 0
    following: int = 0
    posts: int = 0
    verified: bool = False
    private: bool = False
    avatar_url: str = ""
    bio: str = ""
    reason: str = ""  # why a check failed (shown in chat for debugging)


class Checker:
    def __init__(self, proxies=None):
        proxies = proxies or [None]
        self.clients = [
            httpx.AsyncClient(proxy=p, timeout=15, headers=HEADERS, follow_redirects=True)
            for p in proxies
        ]
        self._i = 0

    def _next(self):
        c = self.clients[self._i % len(self.clients)]
        self._i += 1
        return c

    async def check(self, username: str) -> Profile:
        reasons = []
        last = Profile(username, "error")
        for _ in range(min(2, len(self.clients)) or 1):
            client = self._next()
            last = await self._once(client, username)
            if last.status != "error":
                return last
            reasons.append(last.reason)
            # fallback: read the public profile page
            last = await self._html(client, username)
            if last.status != "error":
                return last
            reasons.append(last.reason)
        last.reason = " | ".join(r for r in reasons if r)
        return last

    async def _html(self, client, username):
        """Fallback: parse the public profile page's meta tags."""
        try:
            r = await client.get(
                f"https://www.instagram.com/{username}/",
                headers={**HEADERS, "Accept": "text/html,application/xhtml+xml"},
            )
        except httpx.HTTPError as ex:
            log.warning("html request failed for %s: %s", username, ex)
            return Profile(username, "error", reason=f"page: {type(ex).__name__}")

        if r.status_code == 404:
            return Profile(username, "not_found")
        if r.status_code != 200 or "accounts/login" in str(r.url):
            log.warning("html status %s (%s) for %s", r.status_code, r.url, username)
            why = "login redirect" if "accounts/login" in str(r.url) else f"HTTP {r.status_code}"
            return Profile(username, "error", reason=f"page: {why}")

        text = r.text
        m = re.search(
            r'<meta[^>]+(?:property="og:description"|name="description")[^>]+content="([^"]*)"',
            text,
        )
        if not m:
            if "Page Not Found" in text:
                return Profile(username, "not_found")
            return Profile(username, "error", reason="page: no data (login wall)")

        desc = htmlmod.unescape(m.group(1))
        nums = re.search(
            r"([\d.,]+[KMB]?)\s+Followers?,\s+([\d.,]+[KMB]?)\s+Following,\s+([\d.,]+[KMB]?)\s+Posts?",
            desc,
            re.I,
        )
        if not nums:
            return Profile(username, "error", reason="page: no counts")

        name = ""
        t = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', text)
        if t:
            name = htmlmod.unescape(t.group(1)).split("(@")[0].strip()
        img = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]*)"', text)

        return Profile(
            username=username,
            status="live",
            full_name=name,
            followers=_num(nums.group(1)),
            following=_num(nums.group(2)),
            posts=_num(nums.group(3)),
            avatar_url=htmlmod.unescape(img.group(1)) if img else "",
        )

    async def _once(self, client, username):
        try:
            r = await client.get(URL, params={"username": username})
        except httpx.HTTPError as ex:
            log.warning("request failed for %s: %s", username, ex)
            return Profile(username, "error", reason=f"api: {type(ex).__name__}")

        if r.status_code == 404:
            return Profile(username, "not_found")
        if r.status_code != 200:
            log.warning("status %s for %s", r.status_code, username)
            return Profile(username, "error", reason=f"api: HTTP {r.status_code}")

        try:
            user = r.json()["data"]["user"]
        except Exception:
            # HTML login wall / challenge instead of JSON
            return Profile(username, "error", reason="api: login wall")

        if not user:
            return Profile(username, "not_found")

        return Profile(
            username=user.get("username") or username,
            status="live",
            full_name=user.get("full_name") or "",
            followers=(user.get("edge_followed_by") or {}).get("count", 0),
            following=(user.get("edge_follow") or {}).get("count", 0),
            posts=(user.get("edge_owner_to_timeline_media") or {}).get("count", 0),
            verified=bool(user.get("is_verified")),
            private=bool(user.get("is_private")),
            avatar_url=user.get("profile_pic_url_hd") or user.get("profile_pic_url") or "",
            bio=user.get("biography") or "",
        )
