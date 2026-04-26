"""
client.py
genshin.py 客户端封装
统一的 create_client() 入口，处理国服 / 国际服区分

修复内容：
- 移除硬编码的住宅代理
- 查询不走代理（由 geetest retry 解决 1034）
- 登录走 SOCKS5 代理（在 qrcode_login.py 中单独处理）
- 新增 inject_challenge() 通过 monkey-patch 注入 challenge headers
"""

import functools
from typing import Optional

import genshin
from astrbot.api import logger
from ..db import users as user_db


def create_client(
    qq_id: str,
    game: Optional[genshin.Game] = None,
    proxy_url: str = "",
) -> genshin.Client:
    """
    为指定 QQ 用户创建 genshin.py Client。
    未绑定时抛出 ValueError。

    查询走直连（OCI → 米游社）。
    proxy_url 参数保留供将来扩展（如需 HTTP 代理可在此传入）。
    1034 由 geetest 层用住宅 IP 处理。
    """
    cookies = user_db.get_cookies(qq_id)
    if not cookies:
        raise ValueError("未绑定米游社账号，请先发送 /米 登录")

    uid = None
    if game == genshin.Game.GENSHIN:
        uid = user_db.get_genshin_uid(qq_id)
    elif game == genshin.Game.STARRAIL:
        uid = user_db.get_starrail_uid(qq_id)

    client = genshin.Client(
        cookies,
        game=game,
        uid=int(uid) if uid else None,
        region=genshin.Region.CHINESE,
    )
    return client


def inject_challenge(client: genshin.Client, challenge_headers: dict):
    """
    通过 monkey-patch 给 genshin.py Client 注入 challenge headers。
    仅对下一次请求生效（自动恢复）。

    game record 接口走 request_hoyolab，所以 patch request_hoyolab。
    """
    original = client.request_hoyolab

    @functools.wraps(original)
    async def _patched(*args, **kwargs):
        h = dict(kwargs.get("headers") or {})
        h.update(challenge_headers)
        kwargs["headers"] = h
        client.request_hoyolab = original
        return await original(*args, **kwargs)

    client.request_hoyolab = _patched
    logger.debug(f"[mihoyo] 已注入 challenge headers: {challenge_headers}")


async def fetch_game_accounts(qq_id: str, proxy_url: str = "") -> dict[str, list[str]]:
    """
    拉取米游社账号下的所有游戏 UID。
    返回 {"genshin": [...], "starrail": [...]}
    """
    client = create_client(qq_id, proxy_url=proxy_url)
    accounts = await client.get_game_accounts()

    result: dict[str, list[str]] = {"genshin": [], "starrail": []}
    for acc in accounts:
        uid_str = str(acc.uid)
        if acc.game == genshin.Game.GENSHIN:
            result["genshin"].append(uid_str)
        elif acc.game == genshin.Game.STARRAIL:
            result["starrail"].append(uid_str)

    return result
