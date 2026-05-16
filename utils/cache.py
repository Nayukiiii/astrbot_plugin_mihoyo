"""
utils/cache.py
查询结果内存缓存，避免短时间重复查询触发极验。

缓存策略：
- key = (qq_id, cache_type, extra)，例如 ("12345", "genshin_notes", "")
- 便笺（实时数据）：TTL 3 分钟
- 深渊/忘却/虚构/差分（周期数据）：TTL 30 分钟
- 签到：不缓存（操作类接口）
"""

import time
from typing import Any, Optional, Tuple

# { key: (data, expire_at) }
_cache: dict[str, Tuple[Any, float]] = {}

# TTL 配置（秒）
TTL_NOTES = 180    # 便笺 3 分钟
TTL_ABYSS = 1800   # 深渊/忘却/虚构/差分 30 分钟


def _make_key(qq_id: str, cache_type: str, extra: str = "") -> str:
    return f"{qq_id}:{cache_type}:{extra}"


def get(qq_id: str, cache_type: str, extra: str = "") -> Optional[Any]:
    """取缓存，过期或不存在返回 None。"""
    key = _make_key(qq_id, cache_type, extra)
    entry = _cache.get(key)
    if entry is None:
        return None
    data, expire_at = entry
    if time.monotonic() > expire_at:
        del _cache[key]
        return None
    return data


def set(qq_id: str, cache_type: str, data: Any, ttl: float, extra: str = "") -> None:
    """写入缓存。"""
    key = _make_key(qq_id, cache_type, extra)
    _cache[key] = (data, time.monotonic() + ttl)


def invalidate(qq_id: str, cache_type: str, extra: str = "") -> None:
    """主动清除某个缓存条目。"""
    key = _make_key(qq_id, cache_type, extra)
    _cache.pop(key, None)


def invalidate_user(qq_id: str) -> None:
    """清除某个用户的所有缓存（如重新登录时调用）。"""
    keys = [k for k in _cache if k.startswith(f"{qq_id}:")]
    for k in keys:
        del _cache[k]
