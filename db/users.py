"""
db/users.py
用户绑定数据的增删改查
"""

import json
from datetime import datetime
from typing import Optional

from astrbot.api import logger
from .database import get_conn


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── 查询 ──────────────────────────────────────────────────────────────────────

def get_user(qq_id: str) -> Optional[dict]:
    """获取用户记录，不存在返回 None。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE qq_id = ?", (qq_id,)
        ).fetchone()
    return dict(row) if row else None


def is_bound(qq_id: str) -> bool:
    user = get_user(qq_id)
    return user is not None and bool(user.get("account_id"))


def get_genshin_uid(qq_id: str) -> Optional[str]:
    user = get_user(qq_id)
    return user["genshin_uid"] if user else None


def get_starrail_uid(qq_id: str) -> Optional[str]:
    user = get_user(qq_id)
    return user["starrail_uid"] if user else None


def get_cookies(qq_id: str) -> Optional[dict]:
    """返回 genshin.py 所需的 cookies dict，未绑定返回 None。"""
    user = get_user(qq_id)
    if not user or not user.get("account_id"):
        return None
    cookies = {
        "account_id": user["account_id"],
        "ltuid": user["account_id"],
    }
    if user.get("ltoken_v2"):
        cookies["ltoken_v2"] = user["ltoken_v2"]
        cookies["ltuid_v2"] = user["account_id"]
    if user.get("cookie_token"):
        cookies["cookie_token"] = user["cookie_token"]
    if user.get("stoken"):
        cookies["stoken"] = user["stoken"]
    if user.get("mid"):
        cookies["mid"] = user["mid"]
    return cookies


# ── 写入 ──────────────────────────────────────────────────────────────────────

def upsert_user_cookies(
    qq_id: str,
    account_id: str,
    ltoken_v2: str,
    cookie_token: str = "",
    stoken: str = "",
    mid: str = "",
) -> None:
    """扫码成功后写入 / 更新 Cookie。"""
    now = _now()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT qq_id FROM users WHERE qq_id = ?", (qq_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE users SET
                    account_id=?, ltoken_v2=?, cookie_token=?,
                    stoken=?, mid=?, updated_at=?
                WHERE qq_id=?""",
                (account_id, ltoken_v2, cookie_token, stoken, mid, now, qq_id),
            )
        else:
            conn.execute(
                """INSERT INTO users
                    (qq_id, account_id, ltoken_v2, cookie_token, stoken, mid,
                     genshin_uids, starrail_uids, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, '[]', '[]', ?, ?)""",
                (qq_id, account_id, ltoken_v2, cookie_token, stoken, mid, now, now),
            )


def update_game_uids(
    qq_id: str,
    game: str,
    uids: list[str],
    selected_uid: Optional[str] = None,
) -> None:
    """更新某个游戏的 UID 列表和当前选中 UID。"""
    now = _now()
    uid_json = json.dumps(uids, ensure_ascii=False)
    if game == "genshin":
        col_list, col_sel = "genshin_uids", "genshin_uid"
    else:
        col_list, col_sel = "starrail_uids", "starrail_uid"

    with get_conn() as conn:
        conn.execute(
            f"UPDATE users SET {col_list}=?, {col_sel}=?, updated_at=? WHERE qq_id=?",
            (uid_json, selected_uid or (uids[0] if uids else None), now, qq_id),
        )


def set_selected_uid(qq_id: str, game: str, uid: str) -> None:
    """用户手动选择 UID。"""
    now = _now()
    col = "genshin_uid" if game == "genshin" else "starrail_uid"
    with get_conn() as conn:
        conn.execute(
            f"UPDATE users SET {col}=?, updated_at=? WHERE qq_id=?",
            (uid, now, qq_id),
        )


def get_cookie_str(qq_id: str) -> Optional[str]:
    """返回 cookie 字符串格式，用于直接构造请求头。
    
    米游社 game_record API 需要 ltuid + cookie_token。
    verifyVerification 等接口对 cookie 字段名敏感。
    """
    user = get_user(qq_id)
    if not user or not user.get("account_id"):
        return None
    aid = user['account_id']
    parts = [
        f"account_id={aid}",
        f"ltuid={aid}",
    ]
    if user.get("cookie_token"):
        parts.append(f"cookie_token={user['cookie_token']}")
    if user.get("ltoken_v2"):
        parts.append(f"ltoken_v2={user['ltoken_v2']}")
        parts.append(f"ltuid_v2={aid}")
        # ltoken_v2 必须与 ltmid_v2 同时使用（UIGF 规范）
        # mid 与 ltmid_v2 值相同，字段名不同
        if user.get("mid"):
            parts.append(f"ltmid_v2={user['mid']}")
    if user.get("stoken"):
        parts.append(f"stuid={aid}")
        parts.append(f"stoken={user['stoken']}")
    if user.get("mid"):
        parts.append(f"mid={user['mid']}")
    return "; ".join(parts)


def delete_user(qq_id: str) -> None:
    """解绑：删除用户所有数据（不删抽卡记录，保留历史）。"""
    with get_conn() as conn:
        conn.execute("UPDATE users SET account_id=NULL, ltoken_v2=NULL, "
                     "cookie_token=NULL, stoken=NULL, mid=NULL, "
                     "updated_at=? WHERE qq_id=?", (_now(), qq_id))


def get_all_bound_qq_ids() -> list[str]:
    """返回所有已绑定账号（有 stoken）的 qq_id 列表。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT qq_id FROM users WHERE account_id IS NOT NULL AND stoken IS NOT NULL AND stoken != ''"
        ).fetchall()
    return [row["qq_id"] for row in rows]


def _curl_get(url: str, cookie: str, proxy_url: str = "", timeout: int = 20) -> dict:
    import subprocess, json
    cmd = ["curl", "-s", "--max-time", str(timeout),
           "-H", f"Cookie: {cookie}"]
    if proxy_url:
        cmd += ["--proxy", proxy_url]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        return json.loads(r.stdout)
    except Exception as e:
        raise RuntimeError(f"curl_get 失败: {e}")


async def force_refresh_tokens(qq_id: str, proxy_url: str = "") -> bool:
    """
    强制用 stoken 刷新 ltoken_v2 和 cookie_token，不管现有 token 是否过期。
    返回 True 表示至少刷新了 ltoken_v2。
    """
    import asyncio
    user = get_user(qq_id)
    if not user or not user.get("stoken") or not user.get("account_id"):
        return False
    aid = user["account_id"]
    stoken = user["stoken"]
    mid = user.get("mid", "")
    cookie = f"stuid={aid}; stoken={stoken}; mid={mid}"

    loop = asyncio.get_event_loop()

    # 刷新 ltoken_v2
    url_ltoken = "https://passport-api.mihoyo.com/account/auth/api/getLTokenBySToken"
    try:
        data = await loop.run_in_executor(None, _curl_get, url_ltoken, cookie, proxy_url)
        if data.get("retcode") == 0:
            ltoken = data.get("data", {}).get("ltoken", "")
            if ltoken:
                now = _now()
                with get_conn() as conn:
                    conn.execute("UPDATE users SET ltoken_v2=?, updated_at=? WHERE qq_id=?",
                                 (ltoken, now, qq_id))
                logger.info(f"[mihoyo][refresh] ltoken_v2 刷新成功 qq={qq_id}")
        else:
            logger.warning(f"[mihoyo][refresh] ltoken_v2 刷新失败 qq={qq_id}: {data.get('message')}")
            return False
    except Exception as e:
        logger.warning(f"[mihoyo][refresh] ltoken_v2 异常 qq={qq_id}: {e}")
        return False

    # 刷新 cookie_token
    url_ct = (f"https://api-takumi.mihoyo.com/auth/api/getCookieAccountInfoBySToken"
              f"?stoken={stoken}&uid={aid}&token_types=3")
    try:
        data2 = await loop.run_in_executor(None, _curl_get, url_ct, cookie, proxy_url)
        if data2.get("retcode") == 0:
            ct = data2.get("data", {}).get("cookie_token", "")
            if ct:
                now = _now()
                with get_conn() as conn:
                    conn.execute("UPDATE users SET cookie_token=?, updated_at=? WHERE qq_id=?",
                                 (ct, now, qq_id))
                logger.info(f"[mihoyo][refresh] cookie_token 刷新成功 qq={qq_id}")
    except Exception as e:
        logger.warning(f"[mihoyo][refresh] cookie_token 异常 qq={qq_id}: {e}")

    return True


async def ensure_ltoken_v2(qq_id: str, proxy_url: str = "") -> bool:
    """
    检查用户是否有 ltoken_v2，没有则用 stoken 自动换取。
    game_record API（含 verifyVerification）必须有 ltoken_v2。
    返回 True 表示已有或换取成功。
    """
    import aiohttp
    try:
        from aiohttp_socks import ProxyConnector
    except ImportError:
        ProxyConnector = None

    user = get_user(qq_id)
    if not user or not user.get("stoken"):
        return False
    if user.get("ltoken_v2"):
        return True  # 已有

    aid = user["account_id"]
    stoken = user["stoken"]
    mid = user.get("mid", "")

    url = "https://passport-api.mihoyo.com/account/auth/api/getLTokenBySToken"
    cookie = f"stuid={aid}; stoken={stoken}; mid={mid}"
    connector = None
    if proxy_url and ProxyConnector:
        connector = ProxyConnector.from_url(
            proxy_url.replace("socks5h://", "socks5://", 1), rdns=True
        )
    timeout = aiohttp.ClientTimeout(total=30)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as s:
            async with s.get(url, headers={"Cookie": cookie}) as r:
                data = await r.json(content_type=None)
        if data.get("retcode") == 0:
            ltoken = data.get("data", {}).get("ltoken", "")
            if ltoken:
                now = _now()
                with get_conn() as conn:
                    conn.execute(
                        "UPDATE users SET ltoken_v2=?, updated_at=? WHERE qq_id=?",
                        (ltoken, now, qq_id),
                    )
                from astrbot.api import logger
                logger.info(f"[mihoyo] 自动换取 ltoken_v2 成功 (qq={qq_id}, len={len(ltoken)})")
                return True
        from astrbot.api import logger
        logger.warning(f"[mihoyo] 换取 ltoken_v2 失败: {data}")
        return False
    except Exception as e:
        from astrbot.api import logger
        logger.warning(f"[mihoyo] 换取 ltoken_v2 异常: {e}")
        return False
