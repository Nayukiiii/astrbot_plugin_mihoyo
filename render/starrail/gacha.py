from ..common_gacha import render_gacha_card


async def render_starrail_gacha_card(stats: dict, pool_type: str, uid: str, nickname: str = "") -> bytes:
    return await render_gacha_card(stats, "starrail", pool_type, uid, nickname)
