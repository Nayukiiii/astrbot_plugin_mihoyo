"""
db/database.py
数据库初始化和通用连接管理
"""

import sqlite3
import os
from pathlib import Path

from astrbot.api import logger

# 数据库文件放在插件目录下的 data/ 子目录
_DB_PATH: str = ""


def init_db(data_dir: str) -> None:
    """初始化数据库，建表。在插件 __init__ 中调用一次。"""
    global _DB_PATH
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    _DB_PATH = str(Path(data_dir) / "mihoyo.db")

    with _get_conn() as conn:
        conn.executescript("""
        -- 用户绑定表
        CREATE TABLE IF NOT EXISTS users (
            qq_id           TEXT PRIMARY KEY,
            account_id      TEXT,           -- 米游社 account_id（ltuid）
            ltoken_v2       TEXT,           -- 长期 token
            cookie_token    TEXT,           -- cookie_token（换 authkey 用）
            stoken          TEXT,           -- stoken（换 authkey 用）
            mid             TEXT,           -- 米游社 mid
            genshin_uids    TEXT DEFAULT '[]',   -- JSON 数组，原神 UID 列表
            starrail_uids   TEXT DEFAULT '[]',   -- JSON 数组，崩铁 UID 列表
            genshin_uid     TEXT,           -- 当前选中的原神 UID
            starrail_uid    TEXT,           -- 当前选中的崩铁 UID
            created_at      TEXT,
            updated_at      TEXT
        );

        -- 抽卡记录表
        CREATE TABLE IF NOT EXISTS gacha_records (
            id              TEXT,           -- 米游社原始 id
            qq_id           TEXT,
            game            TEXT,           -- 'genshin' | 'starrail'
            pool_type       TEXT,           -- 'character' | 'weapon' | 'standard' | 'beginner'
            item_id         TEXT,
            name            TEXT,
            rank            INTEGER,        -- 3 / 4 / 5
            item_type       TEXT,           -- 角色 / 武器 / 光锥
            gacha_time      TEXT,
            pity_count      INTEGER,        -- 本次出货的保底计数（本地计算）
            is_up           INTEGER,        -- 0 / 1，五星是否为 UP（本地计算，NULL=未知）
            PRIMARY KEY (id, game)
        );

        -- 抽卡同步状态表（记录每个池子最后同步的 end_id）
        CREATE TABLE IF NOT EXISTS gacha_sync_state (
            qq_id           TEXT,
            game            TEXT,
            pool_type       TEXT,
            last_end_id     TEXT DEFAULT '0',
            last_sync_at    TEXT,
            PRIMARY KEY (qq_id, game, pool_type)
        );

        -- 抽卡 authkey（从用户提供的抽卡链接提取，避免插件重载后丢失）
        CREATE TABLE IF NOT EXISTS gacha_authkeys (
            qq_id           TEXT,
            game            TEXT,
            authkey         TEXT,
            updated_at      TEXT,
            PRIMARY KEY (qq_id, game)
        );
        """)
    logger.info(f"[mihoyo] 数据库初始化完成: {_DB_PATH}")


def _get_conn() -> sqlite3.Connection:
    if not _DB_PATH:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_conn() -> sqlite3.Connection:
    """获取数据库连接，调用方负责 with 语句关闭。"""
    return _get_conn()
