"""
commands/abyss.py
/原 深渊 / /崩 忘却 / /崩 虚构 / /崩 差分
"""

import genshin
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger

from ..utils.client import create_client
from ..db import users as user_db
from ..api import starrail as sr_api
from ..render.abyss.draw_abyss_card import (
    render_spiral_abyss,
    render_forgotten_hall,
    render_pure_fiction,
    render_apocalyptic_shadow,
)
from ..utils.geetest_retry import with_geetest_retry, sr_with_geetest_retry
from ..utils.cache import get as cache_get, set as cache_set, TTL_ABYSS
from ..utils.slow_hint import slow_hint
from ..utils.image import save_image_bytes


async def cmd_spiral_abyss(
    event: AstrMessageEvent,
    previous: bool = False,
    ttocr_key: str = "",
    captcha_provider: str = "ttocr",
    capsolver_key: str = "",
    geetest_server_url: str = "",
    proxy_url: str = "",
    login_proxy_url: str = "",
    unified_msg_origin: str = "",
    context=None,
):
    """/原 深渊 [上期]"""
    qq_id = str(event.get_sender_id())
    uid = user_db.get_genshin_uid(qq_id)
    if not uid:
        yield event.plain_result("请先绑定账号（/米 登录），或您的原神账号未检测到 UID")
        return

    period = "上期" if previous else "本期"
    cache_key = f"spiral_abyss_{'prev' if previous else 'cur'}"
    cached = cache_get(qq_id, cache_key)

    if cached:
        yield event.plain_result(f"⏳ 渲染{period}深渊中（缓存）...")
        data = cached
    else:
        yield event.plain_result(f"⏳ 查询{period}深渊，请稍候...")

    try:
        if not cached:
            client = create_client(qq_id, game=genshin.Game.GENSHIN, proxy_url=proxy_url)
            cookie_str = user_db.get_cookie_str(qq_id) or ""
            schedule_type = 2 if previous else 1

            async with slow_hint(context, event.unified_msg_origin):
                data = await with_geetest_retry(
                    client, cookie_str,
                    lambda: client.get_genshin_spiral_abyss(int(uid), previous=previous),
                    game="genshin",
                    captcha_provider=captcha_provider,
                    ttocr_key=ttocr_key,
                    capsolver_key=capsolver_key,
                    geetest_server_url=geetest_server_url,
                    proxy_url=proxy_url,
                    login_proxy_url=login_proxy_url,
                    unified_msg_origin=event.unified_msg_origin,
                    context=context,
                    qq_id=qq_id,
                )
            cache_set(qq_id, cache_key, data, TTL_ABYSS)

        img = await render_spiral_abyss(data, uid, previous=previous)
        yield event.image_result(save_image_bytes(img))

    except genshin.InvalidCookies:
        yield event.plain_result("Cookie 已失效，请重新 /米 登录")
    except genshin.DataNotPublic:
        yield event.plain_result("该账号数据未公开，请在米游社设置中开启数据公开")
    except RuntimeError as e:
        yield event.plain_result(str(e))
    except Exception as e:
        logger.error(f"[mihoyo] 原神深渊查询失败: {e}")
        yield event.plain_result(f"查询失败：{e}")


async def cmd_forgotten_hall(
    event: AstrMessageEvent,
    previous: bool = False,
    ttocr_key: str = "",
    captcha_provider: str = "manual",
    capsolver_key: str = "",
    geetest_server_url: str = "",
    proxy_url: str = "",
    login_proxy_url: str = "",
    unified_msg_origin: str = "",
    context=None,
):
    """/崩 忘却 [上期]"""
    qq_id = str(event.get_sender_id())
    uid = user_db.get_starrail_uid(qq_id)
    if not uid:
        yield event.plain_result("请先绑定账号（/米 登录），或您的崩铁账号未检测到 UID")
        return

    period = "上期" if previous else "本期"
    cache_key = f"forgotten_hall_{'prev' if previous else 'cur'}"
    cached = cache_get(qq_id, cache_key)

    if cached:
        yield event.plain_result(f"⏳ 渲染{period}忘却之庭中（缓存）...")
        data = cached
    else:
        yield event.plain_result(f"⏳ 查询{period}忘却之庭，请稍候...")

    try:
        if not cached:
            cookie_str = user_db.get_cookie_str(qq_id) or ""
            async with slow_hint(context, event.unified_msg_origin):
                data = await sr_with_geetest_retry(
                    sr_api.get_forgotten_hall,
                    cookie_str=cookie_str, uid=uid, previous=previous,
                    captcha_provider=captcha_provider, ttocr_key=ttocr_key,
                    capsolver_key=capsolver_key, geetest_server_url=geetest_server_url,
                    proxy_url=proxy_url, login_proxy_url=login_proxy_url,
                    qq_id=qq_id, context=context,
                    unified_msg_origin=event.unified_msg_origin,
                )
            cache_set(qq_id, cache_key, data, TTL_ABYSS)

        img = await render_forgotten_hall(data, uid, previous=previous)
        yield event.image_result(save_image_bytes(img))

    except RuntimeError as e:
        yield event.plain_result(str(e))
    except Exception as e:
        logger.error(f"[mihoyo] 忘却之庭查询失败: {e}")
        yield event.plain_result(f"查询失败：{e}")


async def cmd_pure_fiction(
    event: AstrMessageEvent,
    previous: bool = False,
    ttocr_key: str = "",
    captcha_provider: str = "manual",
    capsolver_key: str = "",
    geetest_server_url: str = "",
    proxy_url: str = "",
    login_proxy_url: str = "",
    unified_msg_origin: str = "",
    context=None,
):
    """/崩 虚构 [上期]"""
    qq_id = str(event.get_sender_id())
    uid = user_db.get_starrail_uid(qq_id)
    if not uid:
        yield event.plain_result("请先绑定账号（/米 登录），或您的崩铁账号未检测到 UID")
        return

    period = "上期" if previous else "本期"
    cache_key = f"pure_fiction_{'prev' if previous else 'cur'}"
    cached = cache_get(qq_id, cache_key)

    if cached:
        yield event.plain_result(f"⏳ 渲染{period}虚构叙事中（缓存）...")
        data = cached
    else:
        yield event.plain_result(f"⏳ 查询{period}虚构叙事，请稍候...")

    try:
        if not cached:
            cookie_str = user_db.get_cookie_str(qq_id) or ""
            async with slow_hint(context, event.unified_msg_origin):
                data = await sr_with_geetest_retry(
                    sr_api.get_pure_fiction,
                    cookie_str=cookie_str, uid=uid, previous=previous,
                    captcha_provider=captcha_provider, ttocr_key=ttocr_key,
                    capsolver_key=capsolver_key, geetest_server_url=geetest_server_url,
                    proxy_url=proxy_url, login_proxy_url=login_proxy_url,
                    qq_id=qq_id, context=context,
                    unified_msg_origin=event.unified_msg_origin,
                )
            cache_set(qq_id, cache_key, data, TTL_ABYSS)

        img = await render_pure_fiction(data, uid, previous=previous)
        yield event.image_result(save_image_bytes(img))

    except RuntimeError as e:
        yield event.plain_result(str(e))
    except Exception as e:
        logger.error(f"[mihoyo] 虚构叙事查询失败: {e}")
        yield event.plain_result(f"查询失败：{e}")


async def cmd_apocalyptic_shadow(
    event: AstrMessageEvent,
    previous: bool = False,
    ttocr_key: str = "",
    captcha_provider: str = "manual",
    capsolver_key: str = "",
    geetest_server_url: str = "",
    proxy_url: str = "",
    login_proxy_url: str = "",
    unified_msg_origin: str = "",
    context=None,
):
    """/崩 差分 [上期]"""
    qq_id = str(event.get_sender_id())
    uid = user_db.get_starrail_uid(qq_id)
    if not uid:
        yield event.plain_result("请先绑定账号（/米 登录），或您的崩铁账号未检测到 UID")
        return

    period = "上期" if previous else "本期"
    cache_key = f"apocalyptic_shadow_{'prev' if previous else 'cur'}"
    cached = cache_get(qq_id, cache_key)

    if cached:
        yield event.plain_result(f"⏳ 渲染{period}差分宇宙中（缓存）...")
        data = cached
    else:
        yield event.plain_result(f"⏳ 查询{period}差分宇宙，请稍候...")

    try:
        if not cached:
            cookie_str = user_db.get_cookie_str(qq_id) or ""
            async with slow_hint(context, event.unified_msg_origin):
                data = await sr_with_geetest_retry(
                    sr_api.get_apocalyptic_shadow,
                    cookie_str=cookie_str, uid=uid, previous=previous,
                    captcha_provider=captcha_provider, ttocr_key=ttocr_key,
                    capsolver_key=capsolver_key, geetest_server_url=geetest_server_url,
                    proxy_url=proxy_url, login_proxy_url=login_proxy_url,
                    qq_id=qq_id, context=context,
                    unified_msg_origin=event.unified_msg_origin,
                )
            cache_set(qq_id, cache_key, data, TTL_ABYSS)

        img = await render_apocalyptic_shadow(data, uid, previous=previous)
        yield event.image_result(save_image_bytes(img))

    except RuntimeError as e:
        yield event.plain_result(str(e))
    except Exception as e:
        logger.error(f"[mihoyo] 差分宇宙查询失败: {e}")
        yield event.plain_result(f"查询失败：{e}")
