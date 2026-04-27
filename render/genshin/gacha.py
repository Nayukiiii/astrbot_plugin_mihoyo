from ..common_gacha import render_gacha_card


async def render_genshin_gacha_card(stats: dict, pool_type: str, uid: str, nickname: str = "") -> bytes:
    return await render_gacha_card(stats, "genshin", pool_type, uid, nickname)
