"""
login/qrcode_login.py
米游社扫码登录（hk4e 通道，app_id=2）

修复内容：
- _PROXY 从参数传入而非硬编码
- 其余逻辑不变
"""

import asyncio
import hashlib
import io
import json
import random
import string
import time
from typing import Optional

import aiohttp
import qrcode
import qrcode.image.pil
from astrbot.api import logger

try:
    from aiohttp_socks import ProxyConnector
except ImportError:
    ProxyConnector = None

_APP_ID     = "2"
_CREATE_URL = "https://hk4e-sdk.mihoyo.com/hk4e_cn/combo/panda/qrcode/fetch"
_QUERY_URL  = "https://hk4e-sdk.mihoyo.com/hk4e_cn/combo/panda/qrcode/query"
_STOKEN_URL = "https://passport-api.mihoyo.com/account/ma-cn-session/app/getTokenByGameToken"
_CK_URL     = "https://api-takumi.mihoyo.com/auth/api/getCookieAccountInfoBySToken"
_LK_URL     = "https://passport-api.mihoyo.com/account/auth/api/getLTokenBySToken"
_DS_SALT    = "JwYDpKvLj6MrMqqYU6jTKF17KNO2PXoS"

# 模块级变量：由 main.py 通过 cmd_login 的 proxy_url 参数传入
_proxy_url: str = ""


def _make_device() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=64))


def _make_connector(proxy: str = ""):
    url = proxy or _proxy_url
    if url and ProxyConnector:
        return ProxyConnector.from_url(url, rdns=True)
    return None


def _gen_ds(body: dict) -> str:
    t = str(int(time.time()))
    r = "".join(random.sample(string.ascii_letters, 6))
    b = json.dumps(body)
    h = hashlib.md5(f"salt={_DS_SALT}&t={t}&r={r}&b={b}&q=".encode()).hexdigest()
    return f"{t},{r},{h}"


async def create_qrcode(qq_id: str, proxy_url: str = "") -> tuple:
    device_id = _make_device()
    body = {"app_id": _APP_ID, "device": device_id}
    connector = _make_connector(proxy_url)
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as s:
        async with s.post(
            _CREATE_URL,
            headers={"Content-Type": "application/json", "User-Agent": "okhttp/4.9.3"},
            json=body,
        ) as r:
            data = await r.json(content_type=None)
    if data.get("retcode") != 0:
        raise RuntimeError(f"生成二维码失败: {data.get('message')}")
    qr_url = data["data"]["url"]
    ticket = qr_url.split("ticket=")[1]
    qr = qrcode.QRCode(
        version=3,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), ticket, device_id


async def poll_qrcode_status(
    ticket: str, device_id: str, proxy_url: str = ""
) -> dict:
    body = {"app_id": _APP_ID, "ticket": ticket, "device": device_id}
    connector = _make_connector(proxy_url)
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as s:
        async with s.post(
            _QUERY_URL,
            headers={"Content-Type": "application/json", "User-Agent": "okhttp/4.9.3"},
            json=body,
        ) as r:
            raw = await r.json(content_type=None)
    retcode = raw.get("retcode", -1)
    if retcode not in (0, -106):
        raise RuntimeError(f"轮询失败: {raw.get('message')}")
    result = raw.get("data") or {}
    result["_retcode"] = retcode
    return result


async def _exchange_game_token(
    uid: str, game_token: str, proxy_url: str = ""
) -> Optional[dict]:
    body = {"account_id": int(uid), "game_token": game_token}
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "okhttp/4.9.3",
        "x-rpc-app_version": "2.41.0",
        "DS": _gen_ds(body),
        "x-rpc-aigis": "",
        "x-rpc-game_biz": "bbs_cn",
        "x-rpc-sys_version": "11",
        "x-rpc-device_id": _make_device(),
        "x-rpc-device_fp": "".join(
            random.choices(string.ascii_letters + string.digits, k=13)
        ),
        "x-rpc-device_name": "GenshinUid_login_device",
        "x-rpc-device_model": "GenshinUid_login_device",
        "x-rpc-app_id": "bll8iq97cem8",
        "x-rpc-client_type": "2",
    }
    connector = _make_connector(proxy_url)
    timeout = aiohttp.ClientTimeout(total=60)
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as s:
            async with s.post(_STOKEN_URL, headers=headers, json=body) as r:
                data = await r.json(content_type=None)
        if data.get("retcode") != 0:
            logger.warning(f"[mihoyo] 换取 stoken 失败: {data}")
            return None
        stoken = data["data"]["token"]["token"]
        aid = str(data["data"]["user_info"]["aid"])
        mid = data["data"]["user_info"].get("mid", "")

        async with aiohttp.ClientSession(connector=_make_connector(proxy_url), timeout=timeout) as s:
            async with s.get(
                _CK_URL,
                headers={"Cookie": f"stuid={aid};stoken={stoken};mid={mid}"},
                params={"stoken": stoken, "uid": aid, "token_types": "3"},
            ) as r:
                ck = await r.json(content_type=None)
        cookie_token = (
            ck.get("data", {}).get("cookie_token", "")
            if ck.get("retcode") == 0 else ""
        )

        # 用 stoken 换取 ltoken_v2（game_record API 必需）
        ltoken_v2 = ""
        try:
            st_cookie = f"stuid={aid}; stoken={stoken}; mid={mid}"
            async with aiohttp.ClientSession(
                connector=_make_connector(proxy_url), timeout=timeout
            ) as s:
                async with s.get(
                    _LK_URL,
                    headers={"Cookie": st_cookie},
                ) as r:
                    lt_data = await r.json(content_type=None)
            if lt_data.get("retcode") == 0:
                ltoken_v2 = lt_data.get("data", {}).get("ltoken", "")
                logger.info(f"[mihoyo] 换取 ltoken_v2 成功 (len={len(ltoken_v2)})")
            else:
                logger.warning(f"[mihoyo] 换取 ltoken_v2 失败: {lt_data}")
        except Exception as e:
            logger.warning(f"[mihoyo] 换取 ltoken_v2 异常: {e}")

        return {
            "account_id": aid,
            "mid": mid,
            "stoken": stoken,
            "ltoken_v2": ltoken_v2,
            "cookie_token": cookie_token,
        }
    except Exception as e:
        logger.error(f"[mihoyo] 换 token 异常: {e}")
        return None


async def wait_for_login(
    qq_id: str,
    ticket: str,
    device_id: str,
    on_scanned,
    on_confirmed,
    on_expired,
    max_wait: int = 120,
    proxy_url: str = "",
) -> None:
    elapsed, scanned_notified = 0, False
    while elapsed < max_wait:
        await asyncio.sleep(3)
        elapsed += 3
        try:
            data = await poll_qrcode_status(ticket, device_id, proxy_url)
        except Exception as e:
            logger.warning(f"[mihoyo] 轮询异常: {e}")
            continue
        retcode = data.get("_retcode", -1)
        status = data.get("stat", "")
        if retcode == -106:
            await on_expired()
            return
        if status == "Scanned" and not scanned_notified:
            scanned_notified = True
            await on_scanned()
        if status == "Confirmed":
            try:
                raw_data = json.loads(
                    data.get("payload", {}).get("raw", "{}")
                )
                uid = str(raw_data.get("uid", ""))
                game_token = raw_data.get("token", "")
                if uid and game_token:
                    cookies = await _exchange_game_token(uid, game_token, proxy_url)
                    if cookies:
                        await on_confirmed(cookies)
                        return
            except Exception as e:
                logger.error(f"[mihoyo] 解析 payload 失败: {e}")
            await on_expired()
            return
    await on_expired()
