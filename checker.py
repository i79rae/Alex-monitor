"""Instagram public-profile checker.

Uses Instagram's public web_profile_info endpoint. Instagram rate-limits and
changes this often, so: use PROXIES, keep SCAN_INTERVAL sane, and swap this
class for a paid data API if you need reliability. Keep the Profile shape and
the rest of the bot won't care.
"""
import logging
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
        last = Profile(username, "error")
        for _ in range(min(2, len(self.clients)) or 1):
            last = await self._once(self._next(), username)
            if last.status != "error":
                return last
        return last

    async def _once(self, client, username):
        try:
            r = await client.get(URL, params={"username": username})
        except httpx.HTTPError as ex:
            log.warning("request failed for %s: %s", username, ex)
            return Profile(username, "error")

        if r.status_code == 404:
            return Profile(username, "not_found")
        if r.status_code != 200:
            log.warning("status %s for %s", r.status_code, username)
            return Profile(username, "error")

        try:
            user = r.json()["data"]["user"]
        except Exception:
            # HTML login wall / challenge instead of JSON
            return Profile(username, "error")

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
