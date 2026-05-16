from typing import Dict, List, Tuple

from gsuid_core.logger import logger
from gsuid_core.subscribe import gs_subscribe
from gsuid_core.utils.database.models import Subscribe

from ..sruid_utils.api.mys.models import DailyNoteData
from ..utils.error_reply import prefix as P
from ..utils.mys_api import mys_api

MR_NOTICE = f"可发送[{P}mr]或者[{P}每日]来查看更多信息!"

NOTICE = {
    "stamina": f"🔔 你的开拓力已达提醒阈值!",
    "go": f"💗 你的派遣已全部完成!",
}

NOTICE_MAP = {
    "stamina": "开拓力",
    "go": "派遣",
}


async def get_notice_list():
    datas = await gs_subscribe.get_subscribe("[星铁] 推送")
    datas = await gs_subscribe._to_dict(datas)

    stamina_datas = await gs_subscribe.get_subscribe("[星铁] 体力")
    stamina_datas = await gs_subscribe._to_dict(stamina_datas)

    go_datas = await gs_subscribe.get_subscribe("[星铁] 派遣")
    go_datas = await gs_subscribe._to_dict(go_datas)

    for uid in datas:
        if uid:
            raw_data = await mys_api.get_sr_daily_data(uid)
            if isinstance(raw_data, int):
                logger.error(f"[星铁推送提醒] 获取{uid}的数据失败!")
                continue

            for mode in NOTICE:
                _datas: Dict[str, List[Subscribe]] = locals()[f"{mode}_datas"]
                if uid in _datas:
                    _data_list = _datas[uid]
                    for _data in _data_list:
                        if _data.extra_message:
                            res = await check(
                                mode,
                                raw_data,
                                int(_data.extra_message),
                            )
                            if res[0]:
                                mlist = [
                                    f"🚨 星铁推送提醒 - UID{uid}",
                                    NOTICE[mode],
                                    f"当前{NOTICE_MAP[mode]}值为: {res[1]}",
                                    f"你设置的阈值为: {_data.extra_message}",
                                    MR_NOTICE,
                                ]
                                await _data.send("\n".join(mlist))


async def check(mode: str, data: DailyNoteData, limit: int) -> Tuple[bool, int]:
    if mode == "stamina":
        if data.current_stamina >= limit:
            return True, data.current_stamina
        if data.current_stamina >= data.max_stamina:
            return True, data.current_stamina
        return False, data.current_stamina
    if mode == "go":
        count = 0
        for i in data.expeditions:
            if i.status == "Ongoing":
                count += 1
        return count == 0, count
    return False, 0
