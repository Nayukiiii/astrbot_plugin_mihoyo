"""
commands/gacha.py
/原 抽卡 / /崩 抽卡
"""

from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger

from ..db import users as user_db
from ..db.gacha_sync import sync_gacha
from ..render.gacha.draw_gacha_card import render_gacha_card
from ..utils.image import save_image_bytes
from ..utils.cache import get as cache_get, set as cache_set, TTL_ABYSS

# authkey 临时缓存（会话内共享，不写 DB）
_authkey_cache: dict[str, dict[str, str]] = {}  # qq_id -> {game: authkey}


def get_cached_authkey(qq_id: str, game: str) -> str | None:
    return _authkey_cache.get(qq_id, {}).get(game)


POOL_NAMES = {
    "genshin":  {
        "角色": "character", "武器": "weapon",
        "常驻": "standard", "新手": "beginner",
        "character": "character", "weapon": "weapon",
        "standard": "standard", "beginner": "beginner",
    },
    "starrail": {
        "角色": "character", "光锥": "weapon",
        "常驻": "standard", "新手": "beginner",
        "character": "character", "weapon": "weapon",
        "standard": "standard", "beginner": "beginner",
    },
}


async def cmd_gacha_authkey(
    event: AstrMessageEvent,
    game: str,
    url: str,
):
    """/原 抽卡 链接 <URL> / /崩 抽卡 链接 <URL>"""
    qq_id = str(event.get_sender_id())

    # 从 URL 中提取 authkey
    import urllib.parse as uparse
    try:
        parsed = uparse.urlparse(url)
        params = uparse.parse_qs(parsed.query)
        authkey = params.get("authkey", [None])[0]
        if not authkey:
            yield event.plain_result("❌ URL 中未找到 authkey 参数")
            return
    except Exception as e:
        yield event.plain_result(f"❌ URL 解析失败：{e}")
        return

    if qq_id not in _authkey_cache:
        _authkey_cache[qq_id] = {}
    _authkey_cache[qq_id][game] = authkey

    game_name = "原神" if game == "genshin" else "崩铁"
    yield event.plain_result(
        f"✅ {game_name} authkey 已缓存（本次会话有效）\n"
        f"现在可以使用 /{'原' if game == 'genshin' else '崩'} 抽卡 <池子> 查询记录"
    )


async def cmd_gacha(
    event: AstrMessageEvent,
    game: str,
    pool: str,
    authkey: str | None = None,
    max_pages: int = 0,
):
    """/原 抽卡 <池子> / /崩 抽卡 <池子>"""
    qq_id = str(event.get_sender_id())

    if not user_db.is_bound(qq_id):
        yield event.plain_result("请先绑定账号（/米 登录）")
        return

    pool_map = POOL_NAMES.get(game, {})
    pool_type = pool_map.get(pool)
    if not pool_type:
        game_name = "原神" if game == "genshin" else "崩铁"
        pools = "角色|武器|常驻|新手" if game == "genshin" else "角色|光锥|常驻|新手"
        yield event.plain_result(f"未知池子「{pool}」\n请使用：/{('原' if game=='genshin' else '崩')} 抽卡 {pools}")
        return

    uid = user_db.get_genshin_uid(qq_id) if game == "genshin" else user_db.get_starrail_uid(qq_id)
    if not uid:
        yield event.plain_result("未找到游戏 UID，请先绑定账号")
        return

    yield event.plain_result("⏳ 同步抽卡记录中，请稍候...")

    try:
        new_count = await sync_gacha(
            qq_id, game, pool_type,
            authkey=authkey,
            max_pages=max_pages,
        )

        from ..db import gacha as gacha_db
        stats = gacha_db.get_gacha_stats(qq_id, game, pool_type)
        nickname = ""

        img = await render_gacha_card(stats, game, pool_type, uid, nickname)
        if new_count > 0:
            yield event.plain_result(f"✅ 同步完成，新增 {new_count} 条记录")
        yield event.image_result(save_image_bytes(img))

    except ValueError as e:
        yield event.plain_result(f"❌ {e}")
    except Exception as e:
        logger.error(f"[mihoyo] 抽卡查询失败: {e}")
        yield event.plain_result(f"查询失败：{e}")
