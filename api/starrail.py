"""
api/starrail.py
崩坏：星穹铁道所有战绩接口，直接 aiohttp 实现，不依赖 genshin.py。

便笺获取策略（逆向确认）：
  1. 优先走 Widget 接口（/game_record/app/hkrpg/aapi/widget）
     - 不触发极验，无需过码
     - 使用 salt=t0qEgfub6cvueAPgR5m9aQWWVciEer7v，client_type=2
     - 数据字段与 note 接口一致（逆向 StarRailWidgetData 类确认）
  2. Widget 失败时 fallback 到 /api/note（触发极验则上层处理）

返回值用 SimpleNamespace 包装，属性名与 genshin.py 对象保持兼容。
"""

from types import SimpleNamespace
from typing import Optional

from astrbot.api import logger

from .base import mys_get, mys_widget_get, is_geetest_triggered, sorted_query

_BASE = "https://api-takumi-record.mihoyo.com/game_record/app/hkrpg/api"

# 逆向确认路径（jn.l.intercept 白名单 + ug.f 接口定义）
_WIDGET_URL = "https://api-takumi-record.mihoyo.com/game_record/app/hkrpg/aapi/widget"


def _ns(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def _recognize_server(uid: str) -> str:
    return "prod_qd_cn" if uid.startswith("5") else "prod_gf_cn"


# ── Widget 便笺（主路径）─────────────────────────────────────────────────────

async def get_starrail_widget(
    uid: str,
    cookie: str,
    proxy_url: str = "",
) -> SimpleNamespace:
    """
    通过 Widget 接口获取崩铁便笺数据。

    逆向确认：
    - URL: /game_record/app/hkrpg/aapi/widget（ug.f 接口定义）
    - 无需 role_id/server 参数
    - DS salt: t0qEgfub6cvueAPgR5m9aQWWVciEer7v（libxxxxxx.so ANDROID_SALT 解密）
    - 不触发极验，适合作为便笺主路径

    StarRailWidgetData 字段（逆向自 APK StarRailWidgetData.kt）：
      current_stamina, max_stamina, stamina_recover_time (int, 秒)
      current_reserve_stamina, is_reserve_stamina_full
      current_train_score, max_train_score
      current_rogue_score, max_rogue_score
      accepted_expedition_num, total_expedition_num
      expeditions: [{name, remaining_time (int), status: "Ongoing"|"Finished"}]
      rogue_tourn_weekly_cur, rogue_tourn_weekly_max, rogue_tourn_weekly_unlocked
    """
    data = await mys_widget_get(_WIDGET_URL, cookie, proxy_url=proxy_url)

    retcode = data.get("retcode", -1)
    if retcode != 0:
        raise RuntimeError(
            f"Widget 便笺查询失败: retcode={retcode} msg={data.get('message')}"
        )

    d = data["data"]
    return _parse_widget_data(d)


def _parse_widget_data(d: dict) -> SimpleNamespace:
    """
    解析 StarRailWidgetData JSON 为 SimpleNamespace。

    注意：widget 的 stamina_recover_time 是 int（秒），
    note 接口是 string，这里统一转 int。
    """
    expeditions = [
        _ns(
            name=e.get("name", "派遣角色"),
            remaining_time=SimpleNamespace(
                total_seconds=lambda s=int(e.get("remaining_time", 0)): s
            ),
            finished=e.get("status", "Ongoing") == "Finished",
        )
        for e in d.get("expeditions", [])
    ]

    return _ns(
        current_stamina=d.get("current_stamina", 0),
        max_stamina=d.get("max_stamina", 240),
        stamina_recover_time=SimpleNamespace(
            total_seconds=lambda s=int(d.get("stamina_recover_time", 0)): s
        ),
        current_train_score=d.get("current_train_score", 0),
        max_train_score=d.get("max_train_score", 500),
        current_rogue_score=d.get("current_rogue_score", 0),
        max_rogue_score=d.get("max_rogue_score", 14000),
        expeditions=expeditions,
        accepted_expedition_num=d.get("accepted_expedition_num", 0),
        total_expedition_num=d.get("total_expedition_num", 4),
        current_reserve_stamina=d.get("current_reserve_stamina", 0),
        is_reserve_stamina_full=d.get("is_reserve_stamina_full", False),
        rogue_tourn_weekly_cur=d.get("rogue_tourn_weekly_cur", 0),
        rogue_tourn_weekly_max=d.get("rogue_tourn_weekly_max", 0),
        rogue_tourn_weekly_unlocked=d.get("rogue_tourn_weekly_unlocked", False),
        # note 接口兼容字段
        weekly_cocoon_cnt=0,
        weekly_cocoon_limit=3,
    )


# ── Note 便笺（fallback）────────────────────────────────────────────────────

async def get_starrail_notes(
    uid: str,
    cookie: str,
    challenge: str = "",
    proxy_url: str = "",
    extra_headers: dict = None,
    session=None,
) -> SimpleNamespace:
    """
    通过 /api/note 获取崩铁便笺（fallback，可能触发极验）。
    触发极验（10035/10041）时抛出 _GeetestNeeded 供上层处理。
    """
    params = {"role_id": uid, "server": _recognize_server(uid)}
    data = await mys_get(
        _BASE + "/note", params, cookie,
        challenge=challenge, proxy_url=proxy_url,
        extra_headers=extra_headers, session=session,
    )

    retcode = data.get("retcode", -1)
    if is_geetest_triggered(data):
        raise _GeetestNeeded(retcode)
    if retcode != 0:
        raise RuntimeError(
            f"便笺查询失败: retcode={retcode} msg={data.get('message')}"
        )

    d = data["data"]
    expeditions = [
        _ns(
            name=e.get("name", "派遣角色"),
            remaining_time=SimpleNamespace(
                total_seconds=lambda s=e.get("remaining_time", 0): int(s)
            ),
            finished=int(e.get("remaining_time", 0)) <= 0,
        )
        for e in d.get("expeditions", [])
    ]

    return _ns(
        current_stamina=d.get("current_stamina", 0),
        max_stamina=d.get("max_stamina", 240),
        stamina_recover_time=SimpleNamespace(
            total_seconds=lambda s=d.get("stamina_recover_time", 0): int(s)
        ),
        current_train_score=d.get("current_train_score", 0),
        max_train_score=d.get("max_train_score", 500),
        current_rogue_score=d.get("current_rogue_score", 0),
        max_rogue_score=d.get("max_rogue_score", 14000),
        expeditions=expeditions,
        accepted_expedition_num=d.get(
            "accepted_expedition_num",
            d.get("accepted_epedition_num", 0),
        ),
        total_expedition_num=d.get("total_expedition_num", 4),
        current_reserve_stamina=d.get("current_reserve_stamina", 0),
        is_reserve_stamina_full=False,
        rogue_tourn_weekly_cur=0,
        rogue_tourn_weekly_max=0,
        rogue_tourn_weekly_unlocked=False,
        weekly_cocoon_cnt=d.get("weekly_cocoon_cnt", 0),
        weekly_cocoon_limit=d.get("weekly_cocoon_limit", 3),
    )


# ── 忘却之庭 ─────────────────────────────────────────────────────────────────

async def get_forgotten_hall(
    uid: str, cookie: str, previous: bool = False,
    challenge: str = "", proxy_url: str = "",
    extra_headers: dict = None, session=None,
) -> SimpleNamespace:
    params = {
        "need_all": "true",
        "role_id": uid,
        "schedule_type": "2" if previous else "1",
        "server": _recognize_server(uid),
    }
    data = await mys_get(
        _BASE + "/challenge", params, cookie,
        challenge=challenge, proxy_url=proxy_url,
        extra_headers=extra_headers, session=session,
    )
    retcode = data.get("retcode", -1)
    if is_geetest_triggered(data):
        raise _GeetestNeeded(retcode)
    if retcode != 0:
        raise RuntimeError(f"忘却之庭查询失败: retcode={retcode} msg={data.get('message')}")
    return _wrap_sr_endgame(data["data"])


# ── 虚构叙事 ─────────────────────────────────────────────────────────────────

async def get_pure_fiction(
    uid: str, cookie: str, previous: bool = False,
    challenge: str = "", proxy_url: str = "",
    extra_headers: dict = None, session=None,
) -> SimpleNamespace:
    params = {
        "need_all": "true",
        "role_id": uid,
        "schedule_type": "2" if previous else "1",
        "server": _recognize_server(uid),
    }
    data = await mys_get(
        _BASE + "/challenge_story", params, cookie,
        challenge=challenge, proxy_url=proxy_url,
        extra_headers=extra_headers, session=session,
    )
    retcode = data.get("retcode", -1)
    if is_geetest_triggered(data):
        raise _GeetestNeeded(retcode)
    if retcode != 0:
        raise RuntimeError(f"虚构叙事查询失败: retcode={retcode} msg={data.get('message')}")
    return _wrap_sr_endgame(data["data"])


# ── 差分宇宙 ─────────────────────────────────────────────────────────────────

async def get_apocalyptic_shadow(
    uid: str, cookie: str, previous: bool = False,
    challenge: str = "", proxy_url: str = "",
    extra_headers: dict = None, session=None,
) -> SimpleNamespace:
    params = {
        "need_all": "true",
        "role_id": uid,
        "schedule_type": "2" if previous else "1",
        "server": _recognize_server(uid),
    }
    data = await mys_get(
        _BASE + "/challenge_boss", params, cookie,
        challenge=challenge, proxy_url=proxy_url,
        extra_headers=extra_headers, session=session,
    )
    retcode = data.get("retcode", -1)
    if is_geetest_triggered(data):
        raise _GeetestNeeded(retcode)
    if retcode != 0:
        raise RuntimeError(f"差分宇宙查询失败: retcode={retcode} msg={data.get('message')}")
    return _wrap_sr_endgame(data["data"])


# ── 异相仲裁 ─────────────────────────────────────────────────────────────────

async def get_challenge_peak(
    uid: str, cookie: str, previous: bool = False,
    challenge: str = "", proxy_url: str = "",
    extra_headers: dict = None, session=None,
) -> SimpleNamespace:
    params = {
        "need_all": "true",
        "role_id": uid,
        "schedule_type": "2" if previous else "1",
        "server": _recognize_server(uid),
    }
    data = await mys_get(
        _BASE + "/challenge_peak", params, cookie,
        challenge=challenge, proxy_url=proxy_url,
        extra_headers=extra_headers, session=session,
    )
    retcode = data.get("retcode", -1)
    if is_geetest_triggered(data):
        raise _GeetestNeeded(retcode)
    if retcode != 0:
        raise RuntimeError(f"异相仲裁查询失败: retcode={retcode} msg={data.get('message')}")
    return _wrap_sr_endgame(data["data"])


# ── 货币战争 ─────────────────────────────────────────────────────────────────

async def get_grid_fight(
    uid: str,
    cookie: str,
    challenge: str = "",
    proxy_url: str = "",
    extra_headers: dict = None,
    session=None,
) -> SimpleNamespace:
    params = {
        "role_id": uid,
        "server": _recognize_server(uid),
    }
    data = await mys_get(
        _BASE + "/grid_fight", params, cookie,
        challenge=challenge, proxy_url=proxy_url,
        extra_headers=extra_headers, session=session,
    )
    retcode = data.get("retcode", -1)
    if is_geetest_triggered(data):
        raise _GeetestNeeded(retcode)
    if retcode != 0:
        raise RuntimeError(f"货币战争查询失败: retcode={retcode} msg={data.get('message')}")
    return _wrap_obj(data["data"])


# ── 角色信息 ─────────────────────────────────────────────────────────────────

async def get_role_basic_info(
    uid: str, cookie: str, proxy_url: str = "",
) -> SimpleNamespace:
    params = {"role_id": uid, "server": _recognize_server(uid)}
    data = await mys_get(_BASE + "/role/basicInfo", params, cookie, proxy_url=proxy_url)
    if data.get("retcode") != 0:
        raise RuntimeError(f"角色信息查询失败: {data.get('message')}")
    d = data["data"]
    return _ns(
        nickname=d.get("nickname", "开拓者"),
        level=d.get("level", 0),
        region=d.get("region", ""),
    )


# ── 内部工具 ─────────────────────────────────────────────────────────────────

class _GeetestNeeded(Exception):
    """内部异常，通知上层需要过极验。"""
    def __init__(self, retcode: int = 1034):
        self.retcode = retcode
        super().__init__(f"geetest needed (retcode={retcode})")


def _wrap_obj(value):
    if isinstance(value, dict):
        return _ns(**{key: _wrap_obj(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_wrap_obj(item) for item in value]
    return value


def _wrap_sr_endgame(d: dict) -> SimpleNamespace:
    floors = []
    for floor_raw in d.get("all_floor_detail", []):
        node1 = _wrap_node(floor_raw.get("node_1"))
        node2 = _wrap_node(floor_raw.get("node_2"))
        floors.append(_ns(
            name=floor_raw.get("name", "—"),
            stars=floor_raw.get("star_num", 0),
            max_stars=3,
            node_1=node1,
            node_2=node2,
        ))
    return _ns(
        total_stars=d.get("star_num", 0),
        max_floor=d.get("max_floor", "—"),
        battle_num=d.get("battle_num", 0),
        has_data=d.get("has_data", False),
        floors=floors,
    )


def _wrap_node(node_raw: Optional[dict]) -> Optional[SimpleNamespace]:
    if not node_raw:
        return None
    chars = [
        _ns(name=a.get("name", "?"), level=a.get("level", 1))
        for a in node_raw.get("avatars", [])
    ]
    return _ns(characters=chars)


# ── 公开异常 ─────────────────────────────────────────────────────────────────
GeetestNeeded = _GeetestNeeded
