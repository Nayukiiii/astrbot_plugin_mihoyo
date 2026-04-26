"""
commands/account.py
/米 登录 / 验证 / 解绑 / 账号

登录状态机：
  IDLE
    → /米 登录 (任意场合)
  WAITING_MOBILE  (私聊等待手机号)
    → 用户私聊发手机号
  WAITING_CAPTCHA (私聊等待验证码)
    → /米 验证 <code>

群里发起时：登录成功后回群里发结果
私聊发起时：全程私聊
"""

import asyncio
import json

from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api import logger

from ..db import users as user_db
from ..utils.cache import invalidate_user
from ..login.mobile_login import send_captcha, verify_captcha
from ..utils.client import fetch_game_accounts

# ── 状态存储 ──────────────────────────────────────────────────────────────────

# qq_id -> {"state": "waiting_mobile"|"waiting_captcha", "mobile": str, "group_umo": str|None}
_sessions: dict[str, dict] = {}
_PENDING_TTL = 300  # 5分钟超时


def _clear_session(qq_id: str):
    _sessions.pop(qq_id, None)


def _is_group(event: AstrMessageEvent) -> bool:
    return bool(event.message_obj.group_id)


def _get_private_umo(event: AstrMessageEvent) -> str:
    umo = event.unified_msg_origin
    platform = umo.split(":")[0]
    qq_id = str(event.get_sender_id())
    return f"{platform}:FriendMessage:{qq_id}"


# ── 指令处理 ──────────────────────────────────────────────────────────────────

async def cmd_login(
    event: AstrMessageEvent,
    args: list[str],
    proxy_url: str = "",
    max_wait: int = 300,
    context=None,
):
    """/米 登录"""
    qq_id = str(event.get_sender_id())
    is_group = _is_group(event)

    # 清除旧 session
    _clear_session(qq_id)

    group_umo = event.unified_msg_origin if is_group else None

    if is_group:
        # 群里：提示去私聊，主动私聊用户
        yield event.plain_result(
            "请查看 Bot 私聊，在私聊中完成绑定 👀\n"
            "（如果没有收到私聊，请先添加 Bot 为好友）"
        )
        if context:
            private_umo = _get_private_umo(event)
            try:
                await context.send_message(
                    private_umo,
                    MessageChain().message("请发送你的米游社绑定手机号（仅数字，如：13800138000）")
                )
                # 设置等待手机号状态
                _sessions[qq_id] = {
                    "state": "waiting_mobile",
                    "mobile": "",
                    "group_umo": group_umo,
                }
                asyncio.get_event_loop().call_later(max_wait, _clear_session, qq_id)
            except Exception as e:
                logger.warning(f"[mihoyo] 发送私聊失败: {e}")
    else:
        # 私聊：直接提示输手机号
        yield event.plain_result("请发送你的米游社绑定手机号（仅数字，如：13800138000）")
        _sessions[qq_id] = {
            "state": "waiting_mobile",
            "mobile": "",
            "group_umo": None,
        }
        asyncio.get_event_loop().call_later(max_wait, _clear_session, qq_id)


async def cmd_verify(
    event: AstrMessageEvent,
    args: list[str],
    proxy_url: str = "",
    context=None,
):
    """/米 验证 <验证码>"""
    qq_id = str(event.get_sender_id())

    session = _sessions.get(qq_id)
    if not session or session["state"] != "waiting_captcha":
        yield event.plain_result(
            "没有待验证的登录请求，请先发送：/米 登录"
        )
        return

    if not args:
        yield event.plain_result("请提供验证码：/米 验证 123456")
        return

    captcha = args[0].strip()
    mobile = session["mobile"]
    group_umo = session.get("group_umo")

    yield event.plain_result("⏳ 正在验证...")

    try:
        cookies = await verify_captcha(mobile, captcha, session=session.get("fp_session", {}), proxy_url=proxy_url)
    except Exception as e:
        yield event.plain_result(f"❌ 验证失败：{e}")
        return

    _clear_session(qq_id)

    # 保存 cookies
    try:
        invalidate_user(qq_id)
        user_db.upsert_user_cookies(
            qq_id=qq_id,
            account_id=cookies["account_id"],
            ltoken_v2=cookies.get("ltoken_v2", ""),
            cookie_token=cookies.get("cookie_token", ""),
            stoken=cookies.get("stoken", ""),
            mid=cookies.get("mid", ""),
        )
    except Exception as e:
        logger.error(f"[mihoyo] 保存 Cookie 失败: {e}")
        yield event.plain_result(f"❌ 保存账号信息失败：{e}")
        return

    # 拉取游戏 UID
    msg_parts = ["✅ 登录成功！"]
    try:
        game_uids = await fetch_game_accounts(qq_id, proxy_url=proxy_url)
        for game, uids in game_uids.items():
            if uids:
                game_name = "原神" if game == "genshin" else "崩坏：星穹铁道"
                user_db.update_game_uids(qq_id, game, uids, uids[0])
                if len(uids) == 1:
                    msg_parts.append(f"{game_name}: {uids[0]}")
                else:
                    uid_list = "\n".join(f"  {i+1}. {u}" for i, u in enumerate(uids))
                    msg_parts.append(
                        f"{game_name}: 检测到多个UID，已默认选择 {uids[0]}\n{uid_list}"
                    )
        logger.info(f"[mihoyo] {qq_id} 绑定成功，UIDs: {game_uids}")
    except Exception as e:
        logger.warning(f"[mihoyo] 拉取游戏账号失败: {e}")
        msg_parts.append("（游戏账号拉取失败，可稍后用 /米 账号 查看）")

    result_msg = "\n".join(msg_parts)

    # 私聊回复结果
    yield event.plain_result(result_msg)

    # 如果是群里发起的，回群里也发一条
    if group_umo and context:
        try:
            await context.send_message(
                group_umo,
                MessageChain().message(result_msg)
            )
        except Exception as e:
            logger.warning(f"[mihoyo] 回群通知失败: {e}")


async def handle_private_message(
    event: AstrMessageEvent,
    proxy_url: str = "",
    max_wait: int = 300,
    context=None,
) -> bool:
    """
    处理私聊中的手机号输入。
    返回 True 表示已处理（消息被消费），False 表示不是登录流程的消息。
    """
    qq_id = str(event.get_sender_id())
    session = _sessions.get(qq_id)

    if not session or session["state"] != "waiting_mobile":
        return False

    # 是否是纯数字11位手机号
    text = event.message_str.strip()
    if not text.isdigit() or len(text) != 11:
        # 不像手机号，忽略（让其他处理器处理）
        return False

    mobile = text

    # 发送验证码
    try:
        fp_session = await send_captcha(mobile, proxy_url=proxy_url)
    except Exception as e:
        import traceback
        logger.error(f"[mihoyo] send_captcha 异常: {traceback.format_exc()}")
        # 用 context 主动发消息，因为这里不能 yield
        if context:
            try:
                await context.send_message(
                    event.unified_msg_origin,
                    MessageChain().message(f"❌ 发送验证码失败：{type(e).__name__}: {e}")
                )
            except Exception:
                pass
        _clear_session(qq_id)
        return True

    # 更新状态为等待验证码
    session["state"] = "waiting_captcha"
    session["mobile"] = mobile
    session["fp_session"] = fp_session
    # 重置超时
    asyncio.get_event_loop().call_later(max_wait, _clear_session, qq_id)

    if context:
        try:
            await context.send_message(
                event.unified_msg_origin,
                MessageChain().message(
                    f"✅ 验证码已发送到 {mobile[:3]}****{mobile[-4:]}\n"
                    f"请在 {max_wait // 60} 分钟内回复：/米 验证 <验证码>"
                )
            )
        except Exception as e:
            logger.warning(f"[mihoyo] 发送提示失败: {e}")

    return True


async def cmd_unbind(event: AstrMessageEvent):
    """/米 解绑"""
    qq_id = str(event.get_sender_id())
    if not user_db.is_bound(qq_id):
        yield event.plain_result("您尚未绑定米游社账号。")
        return
    user_db.delete_user(qq_id)
    invalidate_user(qq_id)
    yield event.plain_result("✅ 已解绑米游社账号（历史抽卡记录保留）")


async def cmd_account_info(event: AstrMessageEvent):
    """/米 账号"""
    qq_id = str(event.get_sender_id())
    user = user_db.get_user(qq_id)
    if not user or not user.get("account_id"):
        yield event.plain_result("您尚未绑定米游社账号，请发送 /米 登录")
        return

    gs_uid  = user.get("genshin_uid") or "未绑定"
    sr_uid  = user.get("starrail_uid") or "未绑定"
    gs_uids = json.loads(user.get("genshin_uids") or "[]")
    sr_uids = json.loads(user.get("starrail_uids") or "[]")

    lines = [
        "📋 账号绑定信息",
        f"米游社 ID：{user['account_id']}",
        "",
        f"原神 UID：{gs_uid}",
    ]
    if len(gs_uids) > 1:
        lines.append(f"   全部：{', '.join(gs_uids)}")
    lines.append(f"崩铁 UID：{sr_uid}")
    if len(sr_uids) > 1:
        lines.append(f"   全部：{', '.join(sr_uids)}")

    yield event.plain_result("\n".join(lines))
