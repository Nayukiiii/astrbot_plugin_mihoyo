"""
gacha_sync.py
从米游社拉取抽卡记录并写入本地数据库
支持增量同步（记录上次同步的 end_id）
"""

from typing import Optional

import genshin
from genshin.models import GenshinBannerType, StarRailBannerType

from astrbot.api import logger
from ..utils.client import create_client
from . import gacha as gacha_db

# 池子类型映射：内部 pool_type -> genshin.py BannerType int 值
POOL_MAP_GENSHIN = {
    "character": GenshinBannerType.CHARACTER,
    "weapon":    GenshinBannerType.WEAPON,
    "standard":  GenshinBannerType.STANDARD,
    "beginner":  GenshinBannerType.NOVICE,
}

POOL_MAP_STARRAIL = {
    "character": StarRailBannerType.CHARACTER,
    "weapon":    StarRailBannerType.WEAPON,
    "standard":  StarRailBannerType.STANDARD,
    "beginner":  StarRailBannerType.NOVICE,
}


async def sync_gacha(
    qq_id: str,
    game: str,
    pool_type: str,
    authkey: Optional[str] = None,
    max_pages: int = 0,
    proxy_url: str = "",
) -> int:
    """
    增量同步单个池子的抽卡记录。
    返回新增条数。
    """
    client = create_client(qq_id, proxy_url=proxy_url)
    last_end_id = gacha_db.get_last_end_id(qq_id, game, pool_type)

    # 选择对应的 BannerType
    if game == "genshin":
        banner_type = POOL_MAP_GENSHIN.get(pool_type)
    else:
        banner_type = POOL_MAP_STARRAIL.get(pool_type)

    if banner_type is None:
        raise ValueError(f"未知池子类型: {pool_type}")

    # 拉取记录（genshin.py 返回从新到旧的生成器）
    raw_records: list = []
    page = 0
    end_id = int(last_end_id) if last_end_id != "0" else 0
    try:
        if game == "genshin":
            async for wish in client.wish_history(
                banner_type,
                authkey=authkey,
                end_id=end_id,
            ):
                raw_records.append(wish)
                page += 1
                if max_pages and page >= max_pages * 20:
                    break
        else:
            async for wish in client.warp_history(
                banner_type,
                authkey=authkey,
                end_id=end_id,
            ):
                raw_records.append(wish)
                page += 1
                if max_pages and page >= max_pages * 20:
                    break
    except genshin.AuthkeyTimeout:
        raise ValueError("AuthKey 已过期，请重新获取")
    except genshin.InvalidAuthkey:
        raise ValueError("AuthKey 无效，请检查链接是否正确")

    if not raw_records:
        return 0

    # 计算保底计数和大小保底（需要结合历史数据）
    processed = _calc_pity(qq_id, game, pool_type, raw_records)

    inserted = gacha_db.insert_gacha_records(processed)

    # 更新同步状态（保存最新的 id 作为下次增量起点）
    newest_id = str(raw_records[0].id)
    gacha_db.set_last_end_id(qq_id, game, pool_type, newest_id)

    logger.info(f"[mihoyo] 同步完成: {qq_id} {game} {pool_type} 新增 {inserted} 条")
    return inserted


def _calc_pity(
    qq_id: str,
    game: str,
    pool_type: str,
    raw_records: list,
) -> list[dict]:
    """
    计算每条记录的保底计数（pity_count）和大小保底（is_up）。
    raw_records 是从 genshin.py 拿到的 wish/warp 对象列表，从新到旧。
    """
    # 先把顺序反转为从旧到新，方便计算
    records_asc = list(reversed(raw_records))

    # 从数据库获取最近一次五星之前的保底计数（接续历史）
    # 简化处理：直接从数据库最旧记录往后算
    # 实际上增量同步时 raw_records 已经是新数据，保底从0开始接续
    current_pity = 0
    is_big_pity_next = False  # 下一个五星是否大保底

    # 从库中读取已有记录，判断最后状态
    existing = gacha_db.get_gacha_records(qq_id, game, pool_type, limit=10)
    if existing:
        # existing 是倒序（最新在前）
        # 找最近的五星，接续保底计数
        for rec in existing:
            if rec["rank"] == 5:
                # 上次五星是否歪了
                if pool_type == "character" and rec.get("is_up") == 0:
                    is_big_pity_next = True
                break
        # 当前保底进度：从最新记录往前数直到五星
        for rec in existing:
            if rec["rank"] == 5:
                break
            current_pity += 1

    processed = []
    for wish in records_asc:
        current_pity += 1
        rank = wish.rarity  # Wish/Warp 都有 rarity 字段

        is_up: Optional[int] = None
        pity_at = current_pity

        if rank == 5:
            if pool_type == "character":
                if is_big_pity_next:
                    is_up = 1  # 大保底必出 UP
                    is_big_pity_next = False
                # else: 暂标 None，后续接角色数据库后补全

            current_pity = 0  # 重置保底计数

        processed.append({
            "id":         str(wish.id),
            "qq_id":      qq_id,
            "game":       game,
            "pool_type":  pool_type,
            "item_id":    str(getattr(wish, "item_id", wish.id)),
            "name":       wish.name,
            "rank":       rank,
            "item_type":  wish.type,
            "gacha_time": str(wish.time),
            "pity_count": pity_at,
            "is_up":      is_up,
        })

    return processed
