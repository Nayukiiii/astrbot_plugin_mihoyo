"""
utils/geetest.py
极验自动过验证码 — createVerification → ttocr识别 → verifyVerification

修复说明（2026-04-15）：
1. ttocr itemid 修正为 31（geetest 滑块专用），原 388 为错误值
2. IP 一致性修复：create 和 verify 必须使用同一个连接策略
   - 直连尝试：create(直连) → ttocr → verify(直连)
   - 代理尝试：create(代理) → ttocr → verify(代理)
   - 不再混用（旧逻辑：create直连 + verify代理 = challenge IP不匹配 → retcode=-1）
3. cookie 传入前增加 None 保护
4. 诊断日志增强：输出 cookie 关键字段存在性 + challenge 来源 IP 策略
5. ProxyConnector 增加 family=2 强制 IPv4
"""

import asyncio
import hashlib
import json
import random
import re
import string
import time
import uuid
from typing import Optional, Tuple

import aiohttp
from astrbot.api import logger

from .base import RECORD_HEADERS

try:
    from aiohttp_socks import ProxyConnector, ProxyType
except ImportError:
    ProxyConnector = None
    ProxyType = None

_APP_VERSION = "2.71.1"
# DS salt（client_type=2，对应 SALT_PROD，misc/api 接口）
_DS_SALT = "JwYDpKvLj6MrMqqYU6jTKF17KNO2PXoS"

_CREATE_VERIFY_URL = (
    "https://bbs-api.miyoushe.com"
    "/misc/api/createVerification?is_high=true"
)
_VERIFY_URL = (
    "https://bbs-api.miyoushe.com"
    "/misc/api/verifyVerification"
)

_TTOCR_SUBMIT = "http://api.ttocr.com/api/recognize"
_TTOCR_RESULT = "http://api.ttocr.com/api/results"
_TTOCR_ITEMID = 31   # geetest 滑块专用（经过实测确认）

# 极验 create/verify 与后续 game_record 查询要保持同一设备标识。
# 否则 verifyVerification 返回 OK 后，战绩接口仍可能继续 10041。
_DEVICE_ID = RECORD_HEADERS["x-rpc-device_id"]
_DEVICE_FP = RECORD_HEADERS["x-rpc-device_fp"]
_LIFECYCLE_ID = str(uuid.uuid4())  # APP 启动时生成一次，会话内固定
_DEVICE_NAME  = "Xiaomi 2309DRA50C"
_DEVICE_MODEL = "2309DRA50C"
_SYS_VERSION  = "13"
_CHANNEL      = "xiaomi"

# ── 请求头基础模板（对齐 APP De.C3043k0.q() / RequestUtils.getHeader()）────────
_MYS_HEADERS_BASE = {
    "x-rpc-app_id":          "bll8iq97cem8",
    "x-rpc-app_version":     _APP_VERSION,
    "x-rpc-client_type":     "2",
    "x-rpc-device_id":       _DEVICE_ID,
    "x-rpc-device_fp":       _DEVICE_FP,
    "x-rpc-device_name":     _DEVICE_NAME,
    "x-rpc-device_model":    _DEVICE_MODEL,
    "x-rpc-sys_version":     _SYS_VERSION,
    "x-rpc-game_biz":        "bbs_cn",
    "x-rpc-sdk_version":     "2.42.0",
    "x-rpc-account_version": "2.42.0",
    "x-rpc-lifecycle_id":    _LIFECYCLE_ID,
    "Referer":               "https://app.mihoyo.com",
    "User-Agent":            "okhttp/4.9.3",
}


def _get_ds(body: str = "", query: str = "") -> str:
    """
    DS1 算法，对应 client_type=2（misc/api 接口）。
    格式：salt=xxx&t=t&r=r&b=body&q=query
    GET 请求传 query（如 is_high=true），POST 请求传 body（JSON 字符串）。
    """
    t = str(int(time.time()))
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    r_str = "".join(random.choices(chars, k=6))
    main = f"salt={_DS_SALT}&t={t}&r={r_str}&b={body}&q={query}"
    h = hashlib.md5(main.encode("utf-8")).hexdigest()
    return f"{t},{r_str},{h}"

def _safe_json(text: str) -> Optional[dict]:
    text = text.strip().lstrip("\ufeff")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def _make_connector(proxy_url: str = ""):
    if not proxy_url or not ProxyConnector:
        return None
    try:
        from urllib.parse import urlparse, unquote
        p = urlparse(proxy_url)
        return ProxyConnector(
            proxy_type=ProxyType.SOCKS5,
            host=p.hostname,
            port=p.port or 1080,
            username=unquote(p.username) if p.username else None,
            password=unquote(p.password) if p.password else None,
            rdns=True,
            family=2,  # 强制 IPv4
        )
    except Exception as e:
        logger.warning(f"[geetest] proxy_url 解析失败，降级直连: {e}")
        return None


async def _get_challenge(
    cookie: str,
    proxy_url: str = "",
    label: str = "直连",
    session=None,
) -> Optional[Tuple[str, str]]:
    q_str = "is_high=true"
    ds = _get_ds(query="is_high=true")
    headers = {
        **_MYS_HEADERS_BASE,
        "Cookie": cookie,
        "DS":     ds,
    }
    logger.debug(f"[geetest][create][{label}] DS={ds[:20]}...")
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        if session is not None:
            async with session.get(_CREATE_VERIFY_URL, headers=headers, timeout=timeout) as resp:
                raw = await resp.text()
                logger.info(
                    f"[geetest][create][{label}] HTTP {resp.status} "
                    f"body={raw[:200].replace(chr(10), ' ')}"
                )
        else:
            connector = _make_connector(proxy_url)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as sess:
                async with sess.get(_CREATE_VERIFY_URL, headers=headers) as resp:
                    raw = await resp.text()
                    logger.info(
                        f"[geetest][create][{label}] HTTP {resp.status} "
                        f"body={raw[:200].replace(chr(10), ' ')}"
                    )
        data = _safe_json(raw)
        if data is None:
            logger.error(f"[geetest][create][{label}] 无法解析响应: {raw[:200]}")
            return None
        if data.get("retcode") != 0:
            logger.warning(
                f"[geetest][create][{label}] retcode={data.get('retcode')} "
                f"msg={data.get('message')}"
            )
            return None
        gt = data["data"]["gt"]
        ch = data["data"]["challenge"]
        logger.info(f"[geetest][create][{label}] OK gt={gt[:8]}... ch={ch[:8]}...")
        return gt, ch
    except Exception as e:
        logger.error(f"[geetest][create][{label}] 异常: {type(e).__name__}: {e!r}")
        return None


async def _solve_ttocr(
    gt: str,
    challenge: str,
    ttocr_key: str,
    max_retries: int = 3,
    poll_interval: float = 3.0,
    poll_timeout: float = 60.0,
) -> Optional[Tuple[str, str]]:
    timeout = aiohttp.ClientTimeout(total=30)
    resultid = None
    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.post(
                    _TTOCR_SUBMIT,
                    data={
                        "appkey":    ttocr_key,
                        "gt":        gt,
                        "challenge": challenge,
                        "itemid":    _TTOCR_ITEMID,
                        "referer":   "https://webstatic.mihoyo.com/",
                    },
                ) as resp:
                    raw = await resp.text()
                    result = _safe_json(raw)
            if result and result.get("status") == 1:
                resultid = result["resultid"]
                logger.info(f"[geetest][ttocr] 提交成功 attempt={attempt} rid={resultid} itemid={_TTOCR_ITEMID}")
                break
            else:
                logger.warning(f"[geetest][ttocr] 提交失败 attempt={attempt}: {raw[:150]}")
        except Exception as e:
            logger.warning(f"[geetest][ttocr] 提交异常 attempt={attempt}: {e}")
        if attempt < max_retries:
            await asyncio.sleep(2)

    if not resultid:
        logger.error("[geetest][ttocr] 全部提交失败")
        return None

    elapsed = 0.0
    while elapsed < poll_timeout:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        try:
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.post(
                    _TTOCR_RESULT,
                    data={"appkey": ttocr_key, "resultid": resultid},
                ) as resp:
                    raw = await resp.text()
                    res = _safe_json(raw)
            if res is None:
                continue
            status = res.get("status")
            logger.debug(f"[geetest][ttocr] 轮询 {elapsed:.0f}s status={status}")
            if status == 1:
                validate = res["data"]["validate"]
                ch       = res["data"]["challenge"]
                logger.info(f"[geetest][ttocr] 识别成功 validate={validate[:16]}... ch={ch[:8]}...")
                return validate, ch
            elif status in (0, 2):
                continue
            else:
                logger.warning(f"[geetest][ttocr] 识别失败: {res}")
                return None
        except Exception as e:
            logger.warning(f"[geetest][ttocr] 轮询异常: {e}")
            continue

    logger.warning(f"[geetest][ttocr] 轮询超时 {poll_timeout}s")
    return None


async def _solve_capsolver(
    gt: str,
    challenge: str,
    capsolver_key: str,
    poll_interval: float = 3.0,
    poll_timeout: float = 120.0,
) -> Optional[tuple]:
    """用 CapSolver 解极验，返回 (validate, challenge)。"""
    timeout = aiohttp.ClientTimeout(total=30)
    task_id = None
    try:
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.post(
                "https://api.capsolver.com/createTask",
                json={
                    "clientKey": capsolver_key,
                    "task": {
                        "type": "GeeTestTaskProxyLess",
                        "websiteURL": "https://act.mihoyo.com/",
                        "gt": gt,
                        "challenge": challenge,
                    }
                }
            ) as r:
                data = await r.json(content_type=None)
        task_id = data.get("taskId")
        if not task_id:
            logger.error(f"[geetest][capsolver] 创建任务失败: {data}")
            return None
        logger.info(f"[geetest][capsolver] 任务已创建 taskId={task_id}")
    except Exception as e:
        logger.error(f"[geetest][capsolver] 创建任务异常: {e}")
        return None

    elapsed = 0.0
    while elapsed < poll_timeout:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        try:
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.post(
                    "https://api.capsolver.com/getTaskResult",
                    json={"clientKey": capsolver_key, "taskId": task_id}
                ) as r:
                    result = await r.json(content_type=None)
            status = result.get("status")
            logger.debug(f"[geetest][capsolver] 轮询 {elapsed:.0f}s status={status}")
            if status == "ready":
                sol = result.get("solution", {})
                logger.info(f"[geetest][capsolver] solution完整内容: {sol}")
                validate = sol.get("geetest_validate", "")
                ch       = sol.get("geetest_challenge", challenge)
                logger.info(f"[geetest][capsolver] 识别成功 validate={validate[:16]}...")
                return validate, ch
            if status == "failed":
                logger.warning(f"[geetest][capsolver] 任务失败: {result}")
                return None
        except Exception as e:
            logger.warning(f"[geetest][capsolver] 轮询异常: {e}")

    logger.warning(f"[geetest][capsolver] 轮询超时 {poll_timeout}s")
    return None


async def _verify(
    cookie: str,
    challenge: str,
    validate: str,
    proxy_url: str = "",
    label: str = "直连",
    session=None,
) -> Optional[str]:
    """
    POST verifyVerification。
    proxy_url 必须与调用方 _get_challenge 时一致（challenge 绑定请求 IP）。
    """
    body_dict = {
        "geetest_challenge": challenge,
        "geetest_seccode":   f"{validate}|jordan",
        "geetest_validate":  validate,
    }
    body_str = json.dumps(body_dict, separators=(",", ":"), sort_keys=True)
    ds = _get_ds(body=body_str)

    cookie_fields = {
        "ltoken_v2":    "ltoken_v2"    in cookie,
        "ltuid_v2":     "ltuid_v2"     in cookie,
        "ltmid_v2":     "ltmid_v2"     in cookie,
        "cookie_token": "cookie_token" in cookie,
    }
    logger.info(
        f"[geetest][verify][{label}] DS={ds[:20]}... "
        f"body_len={len(body_str)} "
        f"cookie_fields={cookie_fields} "
        f"proxy={'代理' if proxy_url else '直连'}({proxy_url.split('@')[-1] if proxy_url else 'direct'})"
    )

    headers = {
        **_MYS_HEADERS_BASE,
        "Cookie":       cookie,
        "DS":           ds,
        "Content-Type": "application/json",
    }

    timeout = aiohttp.ClientTimeout(total=60)
    try:
        if session is not None:
            async with session.post(_VERIFY_URL, headers=headers, data=body_str, timeout=timeout) as resp:
                raw = await resp.text()
                logger.info(
                    f"[geetest][verify][{label}] HTTP {resp.status} "
                    f"body={raw[:300].replace(chr(10), ' ')}"
                )
        else:
            connector = _make_connector(proxy_url)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as sess:
                async with sess.post(
                    _VERIFY_URL,
                    headers=headers,
                    data=body_str,
                ) as resp:
                    raw = await resp.text()
                    logger.info(
                        f"[geetest][verify][{label}] HTTP {resp.status} "
                        f"body={raw[:300].replace(chr(10), ' ')}"
                    )
        data = _safe_json(raw)
        if data is None:
            logger.error(f"[geetest][verify][{label}] 无法解析响应: {raw[:200]}")
            return None
        retcode = data.get("retcode")
        if retcode != 0:
            logger.warning(
                f"[geetest][verify][{label}] 失败 retcode={retcode} "
                f"message={data.get('message')} "
                f"data={json.dumps(data.get('data', {}))[:100]}"
            )
            return None
        ch = data["data"]["challenge"]
        logger.info(f"[geetest][verify][{label}] 验证通过 ch={ch[:8]}...")
        return ch
    except Exception as e:
        logger.error(f"[geetest][verify][{label}] 异常: {type(e).__name__}: {e!r}")
        return None


async def _one_round(
    cookie: str,
    proxy_url: str,
    label: str,
    captcha_provider: str = "ttocr",
    ttocr_key: str = "",
    capsolver_key: str = "",
    verify_proxy_url: str = "",
) -> Optional[str]:
    """
    单轮完整过码。
    create 走 proxy_url（直连），verify 走 verify_proxy_url（住宅 IP）。
    challenge 绑定的是极验服务器，不绑定请求方 IP，两步可以用不同代理。
    captcha_provider: "ttocr" 或 "capsolver"
    """
    result = await _get_challenge(cookie, proxy_url, label)
    if not result:
        logger.warning(f"[geetest][{label}] create 失败，跳过本轮")
        return None
    gt, challenge = result

    if captcha_provider == "capsolver":
        solved = await _solve_capsolver(gt, challenge, capsolver_key)
    else:
        solved = await _solve_ttocr(gt, challenge, ttocr_key)

    if not solved:
        logger.warning(f"[geetest][{label}] {captcha_provider} 识别失败，跳过本轮")
        return None
    validate, ch = solved

    await asyncio.sleep(random.uniform(0.8, 1.8))

    # verify 走住宅代理，绕过 OCI IP 对 verifyVerification 的风控
    # bbs-api.miyoushe.com 直连可达，verify 不需要代理
    verified = await _verify(cookie, ch, validate, "", label)
    return verified


async def pass_geetest(
    cookie: str,
    ttocr_key: str = "",
    proxy_url: str = "",
    max_rounds: int = 4,
    captcha_provider: str = "ttocr",
    capsolver_key: str = "",
) -> Optional[str]:
    """
    完整极验过码（含重试）。

    create 和 verify 均走直连。
    bbs-api.miyoushe.com 对 OCI IP 无风控，直连可达。
    captcha_provider: "ttocr" 使用 ttocr.com（按点计费），"capsolver" 使用 capsolver.com（按次计费）。
    """
    if not cookie:
        logger.error("[geetest] cookie 为空，无法过码")
        return None

    logger.info(
        f"[geetest] 开始过码 device_id={_DEVICE_ID[:8]}... "
        f"device_fp={_DEVICE_FP} app={_APP_VERSION} 网络=直连"
    )

    for rnd in range(1, max_rounds + 1):
        if rnd > 1:
            delay = random.uniform(2.0, 4.0)
            logger.info(f"[geetest] 等待 {delay:.1f}s → 第 {rnd} 轮")
            await asyncio.sleep(delay)

        logger.info(f"[geetest] ── 第 {rnd}/{max_rounds} 轮（直连）──")

        verified = await _one_round(cookie, "", f"直连#{rnd}", captcha_provider, ttocr_key, capsolver_key, proxy_url)
        if verified:
            logger.info(f"[geetest] ✓ 过码成功（第 {rnd} 轮，直连）")
            return verified

        logger.warning(f"[geetest] 第 {rnd} 轮失败（直连）")

    logger.error(f"[geetest] {max_rounds} 轮全部失败")
    return None


def get_challenge_headers(challenge: str, game: str = "genshin") -> dict:
    """
    构造注入到后续查询请求的 challenge header。
    来源：in.C11359n.a() + b() 逆向（bitmask=28）：
      z11=true  → 加 x-rpc-challenge
      z12=false → 不加 x-rpc-verify_key
    APP 实际只注入 x-rpc-challenge 一个字段。
    """
    return {"x-rpc-challenge": challenge}
