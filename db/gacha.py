"""
db/gacha.py
抽卡记录数据库操作。
"""

from typing import Optional
from .database import get_conn


def get_last_end_id(qq_id: str, game: str, pool_type: str) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_end_id FROM gacha_sync_state WHERE qq_id=? AND game=? AND pool_type=?",
            (qq_id, game, pool_type),
        ).fetchone()
    return row["last_end_id"] if row else "0"


def set_last_end_id(qq_id: str, game: str, pool_type: str, end_id: str) -> None:
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO gacha_sync_state (qq_id, game, pool_type, last_end_id, last_sync_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(qq_id, game, pool_type) DO UPDATE SET
                 last_end_id=excluded.last_end_id, last_sync_at=excluded.last_sync_at""",
            (qq_id, game, pool_type, end_id, now),
        )


def insert_gacha_records(records: list[dict]) -> int:
    if not records:
        return 0
    inserted = 0
    with get_conn() as conn:
        for r in records:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO gacha_records
                       (id, qq_id, game, pool_type, item_id, name, rank, item_type,
                        gacha_time, pity_count, is_up)
                       VALUES (:id,:qq_id,:game,:pool_type,:item_id,:name,:rank,
                               :item_type,:gacha_time,:pity_count,:is_up)""",
                    r,
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except Exception:
                pass
    return inserted


def get_gacha_records(
    qq_id: str, game: str, pool_type: str, limit: int = 20
) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM gacha_records
               WHERE qq_id=? AND game=? AND pool_type=?
               ORDER BY gacha_time DESC LIMIT ?""",
            (qq_id, game, pool_type, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_gacha_stats(qq_id: str, game: str, pool_type: str) -> dict:
    """返回抽卡统计数据供渲染层使用。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT rank, pity_count, is_up, name, gacha_time
               FROM gacha_records
               WHERE qq_id=? AND game=? AND pool_type=?
               ORDER BY gacha_time ASC""",
            (qq_id, game, pool_type),
        ).fetchall()

    records = [dict(r) for r in rows]
    total   = len(records)
    s5      = [r for r in records if r["rank"] == 5]
    s4      = [r for r in records if r["rank"] == 4]

    # 当前保底（从最后一个五星往后数）
    current_pity = 0
    for r in reversed(records):
        if r["rank"] == 5:
            break
        current_pity += 1

    return {
        "total":          total,
        "five_star":      len(s5),
        "four_star":      len(s4),
        "current_pity":   current_pity,
        "five_star_list": s5[-20:],  # 最近20个五星
    }
