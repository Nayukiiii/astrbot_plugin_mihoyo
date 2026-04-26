"""
utils/geetest_retry.py
极验重试包装器。

支持两种模式：
1. 崩铁直接 aiohttp（sr_with_geetest_retry）
2. 原神 genshin.py（with_geetest_retry）
"""

import asyncio
import io
from typing import Any, Callable, Coroutine, Optional

import aiohttp
import genshin
from astrbot.api import logger
from astrbot.api.event import MessageChain

from ..api.geetest import pass_geetest, _get_challenge, _verify
from ..api.starrail import GeetestNeeded


async def _manual_verify(
    cookie_str: str,
    geetest_server_url: str,
    proxy_url: str,
    context,
    unified_msg_origin: str,
    timeout: float = 300.0,
    _shared_session=None,
) -> Optional[str]:
    import qrcode

    result = await _get_challenge(cookie_str, "", "直连", session=_shared_session)
    if not result:
        logger.error("[geetest][manual] createVerification 失败")
        return None, None
    gt, challenge = result

    server = geetest_server_url.rstrip("/")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as sess:
            async with sess.post(f"{server}/register", json={"gt": gt, "challenge": challenge}) as r:
                data = await r.json(content_type=None)
        session_id = data.get("session_id")
        if not session_id:
            logger.error(f"[geetest][manual] 注册 session 失败: {data}")
            return None, None
    except Exception as e:
        logger.error(f"[geetest][manual] 注册 session 异常: {e}")
        return None, None

    verify_url = f"{server}/verify/{session_id}"
    logger.info(f"[geetest][manual] 验证链接: {verify_url}")

    if context:
        try:
            qr = qrcode.QRCode(border=2)
            qr.add_data(verify_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(buf.getvalue())
                tmp_path = tmp.name
            from astrbot.core.message.components import Image
            await context.send_message(unified_msg_origin, MessageChain().message("⚠️ 触发极验验证，请扫描下方二维码完成验证（5分钟内有效）："))
            await context.send_message(unified_msg_origin, MessageChain([Image.fromFileSystem(tmp_path)]))
            os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"[geetest][manual] 发送二维码异常: {e}")
            try:
                await context.send_message(unified_msg_origin, MessageChain().message(f"⚠️ 触发极验验证，请在5分钟内访问以下链接完成验证：\n{verify_url}"))
            except Exception:
                pass

    elapsed = 0.0
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as sess:
        while elapsed < timeout:
            await asyncio.sleep(3.0)
            elapsed += 3.0
            try:
                async with sess.get(f"{server}/result/{session_id}") as r:
                    res = await r.json(content_type=None)
                if res.get("done"):
                    result_data = res["result"]
                    validate  = result_data["geetest_validate"]
                    challenge = result_data["geetest_challenge"]
                    logger.info(
                        f"[geetest][manual] 用户完成验证 validate={validate[:16]}... "
                        f"challenge={challenge} len={len(challenge)}"
                    )
                    # geetest server 部署在 OCI 本机，createVerification 已用直连
                    # verifyVerification 必须与 create 使用相同 IP，强制直连
                    verified = await _verify(cookie_str, challenge, validate, "", "人工", session=_shared_session)
                    logger.info(f"[geetest][manual] verify返回 challenge={verified} len={len(verified) if verified else 0}")
                    # 关键：查询需要用 JS getValidate() 返回的 34 位 challenge
                    # 而不是 verifyVerification 响应里的 32 位 challenge
                    # 如果 verify 成功但返回的是 32 位，直接用原始 34 位 challenge
                    query_challenge = verified if verified and len(verified) > 32 else challenge
                    logger.info(f"[geetest][manual] 最终用于查询的 challenge={query_challenge} len={len(query_challenge)}")
                    if verified:
                        if context:
                            try:
                                await context.send_message(unified_msg_origin, MessageChain().message("✅ 验证成功，正在继续查询..."))
                            except Exception:
                                pass
                        return query_challenge, validate
                    logger.warning("[geetest][manual] verifyVerification 失败")
                    return None, None
            except Exception as e:
                logger.warning(f"[geetest][manual] 轮询异常: {e}")

    logger.warning(f"[geetest][manual] 等待超时 {timeout}s")
    if context:
        try:
            await context.send_message(unified_msg_origin, MessageChain().message("❌ 验证超时，请重新发起查询"))
        except Exception:
            pass
    return None, None


async def _do_geetest(
    cookie_str: str,
    captcha_provider: str,
    ttocr_key: str,
    capsolver_key: str,
    geetest_server_url: str,
    proxy_url: str,
    context,
    unified_msg_origin: str,
    _shared_session=None,
) -> Optional[str]:
    if captcha_provider == "manual":
        if not geetest_server_url:
            raise RuntimeError("provider=manual 但未配置 geetest_server_url")
        return await _manual_verify(cookie_str, geetest_server_url, proxy_url, context, unified_msg_origin, _shared_session=_shared_session)
    else:
        if captcha_provider == "capsolver" and not capsolver_key:
            raise RuntimeError("未配置 captcha.capsolver_apikey")
        if captcha_provider != "capsolver" and not ttocr_key:
            raise RuntimeError("未配置 captcha.ttocr_appkey")
        ch = await pass_geetest(
            cookie_str,
            ttocr_key=ttocr_key,
            proxy_url=proxy_url,
            captcha_provider=captcha_provider,
            capsolver_key=capsolver_key,
        )
        # pass_geetest 不返回 validate，用空字符串占位
        return ch, ""


async def sr_with_geetest_retry(
    api_func: Callable,
    cookie_str: str,
    uid: str,
    captcha_provider: str = "manual",
    ttocr_key: str = "",
    capsolver_key: str = "",
    geetest_server_url: str = "",
    proxy_url: str = "",
    login_proxy_url: str = "",
    qq_id: str = "",
    context=None,
    unified_msg_origin: str = "",
    **kwargs,
) -> Any:
    """崩铁战绩查询包装器，直接调用 api/starrail.py 的函数。"""
    if qq_id:
        from ..db import users as user_db
        await user_db.ensure_ltoken_v2(qq_id, login_proxy_url)
        fresh = user_db.get_cookie_str(qq_id)
        if fresh:
            cookie_str = fresh

    # 用同一个 session 跑完整流程：第一次查询 → 触发极验 → geetest → 重试查询
    # challenge 绑定 createVerification 时服务端下发的 cookie，必须同 CookieJar 发起后续请求
    # unsafe=True 允许更宽松的 domain 匹配，确保 .mihoyo.com/.miyoushe.com 的 cookie 都能传
    import aiohttp as _aiohttp
    _jar = _aiohttp.CookieJar(unsafe=True)
    async with _aiohttp.ClientSession(cookie_jar=_jar) as shared_session:
        try:
            return await api_func(uid, cookie_str, challenge="", proxy_url="", session=shared_session, **kwargs)
        except GeetestNeeded:
            logger.info(f"[mihoyo] 崩铁触发极验，provider={captcha_provider}...")

        if not cookie_str:
            raise RuntimeError("cookie 为空，无法进行极验过码")

        challenge, validate = await _do_geetest(
            cookie_str, captcha_provider, ttocr_key, capsolver_key,
            geetest_server_url, proxy_url, context, unified_msg_origin,
            _shared_session=shared_session,
        )

        if not challenge:
            raise RuntimeError("极验过码失败，请稍后重试")

        # 诊断：dump cookie jar 内容
        try:
            jar_cookies = {}
            for domain, cookies in shared_session.cookie_jar._cookies.items():
                jar_cookies[str(domain)] = list(cookies.keys())
            logger.info(f"[mihoyo][debug] cookie_jar after geetest: {jar_cookies}")
        except Exception as _e:
            logger.info(f"[mihoyo][debug] cookie_jar dump failed: {_e}")

        logger.info(f"[mihoyo] 极验过码成功，challenge={challenge[:8]}...，正在重试...")

        try:
            return await api_func(
                uid, cookie_str, challenge=challenge, proxy_url="",
                session=shared_session, **kwargs,
            )
        except GeetestNeeded as first_retry_error:
            if not validate:
                raise first_retry_error
            logger.warning(
                "[mihoyo] 仅 challenge 重试仍触发极验，尝试附加 validate 头"
            )

        extra = {
            "x-rpc-challenge_game": "6",
            "x-rpc-page":           "v1.4.1-rpg_#/rpg",
            "x-rpc-tool-verison":   "v1.4.1-rpg",
            "x-rpc-geetest_validate": validate,
            "x-rpc-seccode":          f"{validate}|jordan",
        }
        return await api_func(
            uid, cookie_str, challenge=challenge, proxy_url="",
            session=shared_session, extra_headers=extra, **kwargs,
        )


async def with_geetest_retry(
    client: genshin.Client,
    cookie_str: str,
    coro_factory: Callable[[], Coroutine],
    game: str = "genshin",
    captcha_provider: str = "ttocr",
    ttocr_key: str = "",
    capsolver_key: str = "",
    geetest_server_url: str = "",
    proxy_url: str = "",
    login_proxy_url: str = "",
    qq_id: str = "",
    context=None,
    unified_msg_origin: str = "",
) -> Any:
    """原神战绩查询包装器，通过 genshin.py client。"""
    try:
        return await coro_factory()
    except genshin.GeetestError:
        logger.info(f"[mihoyo] 原神触发极验，provider={captcha_provider}...")

    if qq_id:
        from ..db import users as user_db
        await user_db.ensure_ltoken_v2(qq_id, login_proxy_url)
        fresh = user_db.get_cookie_str(qq_id)
        if fresh:
            cookie_str = fresh

    if not cookie_str:
        raise RuntimeError("cookie 为空，无法进行极验过码")

    challenge = await _do_geetest(
        cookie_str, captcha_provider, ttocr_key, capsolver_key,
        geetest_server_url, proxy_url, context, unified_msg_origin
    )

    if not challenge:
        raise RuntimeError("极验过码失败，请稍后重试")

    logger.info(f"[mihoyo] 极验过码成功，challenge={challenge[:8]}...，正在重试...")
    client.custom_headers = {"x-rpc-challenge": challenge}
    try:
        result = await coro_factory()
    finally:
        client.custom_headers = {}
    return result
