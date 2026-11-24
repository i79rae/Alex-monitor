import time

import aiosqlite

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    first_seen INTEGER
);
CREATE TABLE IF NOT EXISTS radars(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    mode TEXT NOT NULL,
    baseline TEXT DEFAULT '',
    created INTEGER,
    UNIQUE(user_id, username, mode)
);
CREATE TABLE IF NOT EXISTS targets(
    username TEXT PRIMARY KEY,
    status TEXT,
    since INTEGER
);
"""

_c = None


async def init():
    global _c
    _c = await aiosqlite.connect(config.DB_PATH)
    _c.row_factory = aiosqlite.Row
    await _c.executescript(SCHEMA)
    await _c.commit()


async def add_user(uid):
    await _c.execute("INSERT OR IGNORE INTO users VALUES(?,?)", (uid, int(time.time())))
    await _c.commit()


async def count_users():
    cur = await _c.execute("SELECT COUNT(*) FROM users")
    return (await cur.fetchone())[0]


async def add_radar(uid, username, mode, baseline=""):
    cur = await _c.execute(
        "INSERT OR IGNORE INTO radars(user_id,username,mode,baseline,created) VALUES(?,?,?,?,?)",
        (uid, username, mode, baseline, int(time.time())),
    )
    await _c.commit()
    return cur.rowcount == 1


async def remove_radar(rid):
    await _c.execute("DELETE FROM radars WHERE id=?", (rid,))
    await _c.commit()


async def remove_user_radar(uid, username, mode):
    cur = await _c.execute(
        "DELETE FROM radars WHERE user_id=? AND username=? AND mode=?", (uid, username, mode)
    )
    await _c.commit()
    return cur.rowcount > 0


async def set_baseline(rid, value):
    await _c.execute("UPDATE radars SET baseline=? WHERE id=?", (value, rid))
    await _c.commit()


async def user_radars(uid, mode=None):
    if mode:
        cur = await _c.execute(
            "SELECT * FROM radars WHERE user_id=? AND mode=? ORDER BY id", (uid, mode)
        )
    else:
        cur = await _c.execute("SELECT * FROM radars WHERE user_id=? ORDER BY id", (uid,))
    return await cur.fetchall()


async def all_radars():
    cur = await _c.execute("SELECT * FROM radars")
    return await cur.fetchall()


async def count_radars(uid=None):
    if uid is None:
        cur = await _c.execute("SELECT COUNT(*) FROM radars")
    else:
        cur = await _c.execute("SELECT COUNT(*) FROM radars WHERE user_id=?", (uid,))
    return (await cur.fetchone())[0]


async def get_target(username):
    cur = await _c.execute("SELECT * FROM targets WHERE username=?", (username,))
    return await cur.fetchone()


async def set_target(username, status):
    await _c.execute(
        "INSERT INTO targets(username,status,since) VALUES(?,?,?) "
        "ON CONFLICT(username) DO UPDATE SET status=excluded.status, since=excluded.since",
        (username, status, int(time.time())),
    )
    await _c.commit()


async def set_target_if_changed(username, status):
    prev = await get_target(username)
    if prev is None or prev["status"] != status:
        await set_target(username, status)
