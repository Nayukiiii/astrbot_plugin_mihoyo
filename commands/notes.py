"""
commands/notes.py
/原 便笺 / /崩 便笺 / /原 签到 / /崩 签到

崩铁便笺策略（逆向确认）：
  优先走 Widget 接口（不触发极验），失败时 fallback 到 note + geetest retry。

原神便笺：
  genshin.py 路径暂时保留，待后续迁移到原神 widget 接口。
"""

import genshin
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger

from ..utils.client import create_client
from ..db import users as user_db
from ..api import starrail as sr_api
from ..render.notes.draw_notes_card import render_genshin_notes, render_starrail_notes
from ..utils.geetest_retry import with_geetest_retry, sr_with_geetest_retry
from ..utils.cache import get as cache_get, set as cache_set, TTL_NOTES
from ..utils.slow_hint import slow_hint


# ── 崩铁便笺 ──────────────────────────────────────────────────────────────────

async def cmd_starrail_notes(
    event: AstrMessageEvent,
    ttocr_key: str = "",
    captcha_provider: str = "manual",
    capsolver_key: str = "",
    geetest_server_url: str = "",
    proxy_url: str = "",
    login_proxy_url: str = "",
    unified_msg_origin: str = "",
    context=None,
):
    """/崩 便笺 — 优先走 Widget，失败 fallback note+geetest"""
    qq_id = str(event.get_sender_id())
    uid = user_db.get_starrail_uid(qq_id)
    if not uid:
        yield event.plain_result("请先绑定账号（/米 登录），或您的崩铁账号未检测到 UID")
        return

    cached = cache_get(qq_id, "starrail_notes")
    if cached:
        yield event.plain_result("⏳ 渲染中（缓存）...")
        notes = cached
    else:
        yield event.plain_result("⏳ 查询中，请稍候...")

    try:
        if not cached:
            cookie_str = user_db.get_cookie_str(qq_id) or ""

            # ── 第一步：尝试 Widget（无极验）────────────────────────────────
            notes = None
            async with slow_hint(context, event.unified_msg_origin):
                try:
                    notes = await sr_api.get_starrail_widget(uid, cookie_str, proxy_url=proxy_url)
                    logger.info(f"[mihoyo] 崩铁便笺 widget 成功 uid={uid}")
                except Exception as e:
                    logger.warning(f"[mihoyo] 崩铁便笺 widget 失败，fallback note: {e}")

                # ── 第二步：Widget 失败则走 note + geetest retry ──────────
                if notes is None:
                    notes = await sr_with_geetest_retry(
                        sr_api.get_starrail_notes,
                        cookie_str=cookie_str,
                        uid=uid,
                        captcha_provider=captcha_provider,
                        ttocr_key=ttocr_key,
                        capsolver_key=capsolver_key,
                        geetest_server_url=geetest_server_url,
                        proxy_url=proxy_url,
                        login_proxy_url=login_proxy_url,
                        qq_id=qq_id,
                        context=context,
                        unified_msg_origin=event.unified_msg_origin,
                    )

            cache_set(qq_id, "starrail_notes", notes, TTL_NOTES)

        # 获取昵称
        nickname = ""
        try:
            info = await sr_api.get_role_basic_info(uid, user_db.get_cookie_str(qq_id) or "")
            nickname = info.nickname
        except Exception:
            pass

        img = await render_starrail_notes(notes, uid, nickname)
        from ..utils.image import save_image_bytes
        yield event.image_result(save_image_bytes(img))

    except RuntimeError as e:
        yield event.plain_result(str(e))
    except Exception as e:
        logger.error(f"[mihoyo] 崩铁便笺查询失败: {e}")
        yield event.plain_result(f"查询失败：{e}")


# ── 原神便笺 ──────────────────────────────────────────────────────────────────

async def cmd_genshin_notes(
    event: AstrMessageEvent,
    ttocr_key: str = "",
    captcha_provider: str = "ttocr",
    capsolver_key: str = "",
    geetest_server_url: str = "",
    proxy_url: str = "",
    login_proxy_url: str = "",
    unified_msg_origin: str = "",
    context=None,
):
    """/原 便笺（TODO: 迁移到原神 widget 接口）"""
    qq_id = str(event.get_sender_id())
    uid = user_db.get_genshin_uid(qq_id)
    if not uid:
        yield event.plain_result("请先绑定账号（/米 登录），或您的原神账号未检测到 UID")
        return

    cached = cache_get(qq_id, "genshin_notes")
    if cached:
        yield event.plain_result("⏳ 渲染中（缓存）...")
        notes = cached
    else:
        yield event.plain_result("⏳ 查询中，请稍候...")

    try:
        if not cached:
            client = create_client(qq_id, game=genshin.Game.GENSHIN, proxy_url=proxy_url)
            cookie_str = user_db.get_cookie_str(qq_id) or ""

            async with slow_hint(context, event.unified_msg_origin):
                notes = await with_geetest_retry(
                    client, cookie_str,
                    lambda: client.get_genshin_notes(int(uid)),
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
            cache_set(qq_id, "genshin_notes", notes, TTL_NOTES)

        nickname = ""
        try:
            cards = await client.get_record_cards()
            for card in cards:
                if card.game == genshin.Game.GENSHIN and str(card.uid) == uid:
                    nickname = card.nickname
                    break
        except Exception:
            pass

        img = await render_genshin_notes(notes, uid, nickname)
        from ..utils.image import save_image_bytes
        yield event.image_result(save_image_bytes(img))

    except genshin.InvalidCookies:
        yield event.plain_result("Cookie 已失效，请重新 /米 登录")
    except genshin.DataNotPublic:
        yield event.plain_result("该账号数据未公开，请在米游社设置中开启数据公开")
    except RuntimeError as e:
        yield event.plain_result(str(e))
    except Exception as e:
        logger.error(f"[mihoyo] 原神便笺查询失败: {e}")
        yield event.plain_result(f"查询失败：{e}")


# ── 签到 ───────────────────────────────────────────────────────────────────────

async def cmd_starrail_checkin(
    event: AstrMessageEvent,
    ttocr_key: str = "",
    captcha_provider: str = "manual",
    capsolver_key: str = "",
    geetest_server_url: str = "",
    proxy_url: str = "",
    login_proxy_url: str = "",
    unified_msg_origin: str = "",
    context=None,
):
    """/崩 签到"""
    qq_id = str(event.get_sender_id())
    if not user_db.is_bound(qq_id):
        yield event.plain_result("请先绑定账号（/米 登录）")
        return

    yield event.plain_result("⏳ 签到中...")
    try:
        client = create_client(qq_id, game=genshin.Game.STARRAIL, proxy_url=proxy_url)
        cookie_str = user_db.get_cookie_str(qq_id) or ""

        async with slow_hint(context, event.unified_msg_origin):
            reward = await with_geetest_retry(
                client, cookie_str,
                lambda: client.claim_daily_reward(game=genshin.Game.STARRAIL),
                game="starrail",
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
        yield event.plain_result(
            f"✅ 崩铁签到成功！\n今日奖励：{reward.name} × {reward.amount}"
        )
    except genshin.AlreadyClaimed:
        yield event.plain_result("今天已经签到过了 ✓")
    except genshin.InvalidCookies:
        yield event.plain_result("Cookie 已失效，请重新 /米 登录")
    except Exception as e:
        logger.error(f"[mihoyo] 崩铁签到失败: {e}")
        yield event.plain_result(f"签到失败：{e}")


async def cmd_genshin_checkin(
    event: AstrMessageEvent,
    ttocr_key: str = "",
    captcha_provider: str = "ttocr",
    capsolver_key: str = "",
    geetest_server_url: str = "",
    proxy_url: str = "",
    login_proxy_url: str = "",
    unified_msg_origin: str = "",
    context=None,
):
    """/原 签到"""
    qq_id = str(event.get_sender_id())
    if not user_db.is_bound(qq_id):
        yield event.plain_result("请先绑定账号（/米 登录）")
        return

    yield event.plain_result("⏳ 签到中...")
    try:
        client = create_client(qq_id, game=genshin.Game.GENSHIN, proxy_url=proxy_url)
        cookie_str = user_db.get_cookie_str(qq_id) or ""

        async with slow_hint(context, event.unified_msg_origin):
            reward = await with_geetest_retry(
                client, cookie_str,
                lambda: client.claim_daily_reward(game=genshin.Game.GENSHIN),
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
        yield event.plain_result(
            f"✅ 原神签到成功！\n今日奖励：{reward.name} × {reward.amount}"
        )
    except genshin.AlreadyClaimed:
        yield event.plain_result("今天已经签到过了 ✓")
    except genshin.InvalidCookies:
        yield event.plain_result("Cookie 已失效，请重新 /米 登录")
    except Exception as e:
        logger.error(f"[mihoyo] 原神签到失败: {e}")
        yield event.plain_result(f"签到失败：{e}")
