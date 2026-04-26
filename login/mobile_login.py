import asyncio
import base64
import hashlib
import json
import random
import string
import time

import requests
from astrbot.api import logger

try:
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_v1_5
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

from .device_pool import pick_device
from .fingerprint import fetch_device_fp, make_device_id

_SALT = "JwYDpKvLj6MrMqqYU6jTKF17KNO2PXoS"

_RSA_PUBLIC_KEY_B64 = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDDvekdPMHN3AYhm/vktJT+YJr7"
    "cI5DcsNKqdsx5DZX0gDuWFuIjzdwButrIYPNmRJ1G8ybDIF7oDW2eEpm5sMbL9zs"
    "9ExXCdvqrn51qELbqj0XxtMTIpaCHFSI50PfPpTFV9Xt/hmyVwokoOXFlAEgCn+Q"
    "CgGs52bFoYMtyi+xEQIDAQAB"
)

_URL_CAPTCHA = (
    "https://passport-api.mihoyo.com"
    "/account/ma-cn-verifier/verifier/createLoginCaptcha"
)
_URL_LOGIN = (
    "https://passport-api.mihoyo.com"
    "/account/ma-cn-passport/app/loginByMobileCaptcha"
)
_URL_COOKIE_TOKEN = (
    "https://api-takumi.mihoyo.com/auth/api/getCookieAccountInfoBySToken"
)
_URL_LTOKEN = (
    "https://passport-api.mihoyo.com/account/auth/api/getLTokenBySToken"
)


def _rsa_encrypt(text: str) -> str:
    if not _CRYPTO_OK:
        raise RuntimeError("pycryptodome 未安装，请执行: pip install pycryptodome")
    pub_key = RSA.import_key(base64.b64decode(_RSA_PUBLIC_KEY_B64))
    cipher  = PKCS1_v1_5.new(pub_key)
    return base64.b64encode(cipher.encrypt(text.encode("utf-8"))).decode("utf-8")


def _make_ds(body: dict) -> str:
    t   = str(int(time.time()))
    r   = "".join(random.choices(string.ascii_letters + string.digits, k=6))
    b   = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    raw = f"salt={_SALT}&t={t}&r={r}&b={b}&q="
    md5 = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return f"{t},{r},{md5}"


def _make_headers(body: dict, device: dict) -> dict:
    return {
        "Accept":                "application/json",
        "Content-Type":          "application/json",
        "User-Agent":            "okhttp/4.9.3",
        "x-rpc-app_id":          "bll8iq97cem8",
        "x-rpc-client_type":     "2",
        "x-rpc-device_id":       device["device_id"],
        "x-rpc-device_fp":       device["device_fp"],
        "x-rpc-device_name":     device["device_name"],
        "x-rpc-device_model":    device["device_model"],
        "x-rpc-sys_version":     device["sys_version"],
        "x-rpc-game_biz":        "bbs_cn",
        "x-rpc-app_version":     "2.104.0",
        "x-rpc-sdk_version":     "2.42.0",
        "x-rpc-account_version": "2.42.0",
        "x-rpc-aigis":           "",
        "DS":                    _make_ds(body),
    }


def _make_proxies(proxy_url: str = "") -> dict:
    """requests 格式的代理字典。"""
    if not proxy_url:
        return {}
    return {"http": proxy_url, "https": proxy_url}


def _sync_post(url: str, headers: dict, body: dict, proxy_url: str = "") -> dict:
    """同步 POST，在线程池中调用以避免 asyncio TLS over SOCKS5 的问题。"""
    try:
        resp = requests.post(
            url,
            headers=headers,
            json=body,
            proxies=_make_proxies(proxy_url),
            timeout=30,
        )
    except requests.exceptions.InvalidSchema as e:
        if proxy_url.startswith("socks"):
            raise RuntimeError("当前环境缺少 SOCKS 代理支持，请安装 PySocks 后重试") from e
        raise
    return resp.json()


def _sync_get(url: str, headers: dict, params: dict = None, proxy_url: str = "") -> dict:
    """同步 GET，在线程池中调用。"""
    try:
        resp = requests.get(
            url,
            headers=headers,
            params=params or {},
            proxies=_make_proxies(proxy_url),
            timeout=30,
        )
    except requests.exceptions.InvalidSchema as e:
        if proxy_url.startswith("socks"):
            raise RuntimeError("当前环境缺少 SOCKS 代理支持，请安装 PySocks 后重试") from e
        raise
    return resp.json()


async def _async_post(url: str, headers: dict, body: dict, proxy_url: str = "") -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_post, url, headers, body, proxy_url)


async def _async_get(url: str, headers: dict, params: dict = None, proxy_url: str = "") -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_get, url, headers, params or {}, proxy_url)


async def send_captcha(mobile: str, proxy_url: str = "") -> dict:
    """
    发送手机验证码。

    Returns:
        session dict，包含本次登录的 device 信息，需要原样传给 verify_captcha()。
    """
    device = pick_device()
    device_id = make_device_id()
    device["androidId"] = device_id
    device["device_id"] = device_id
    device["device_fp"] = await fetch_device_fp(device, proxy_url=proxy_url)

    body = {
        "mobile":    _rsa_encrypt(mobile),
        "area_code": _rsa_encrypt("+86"),
    }

    data = await _async_post(_URL_CAPTCHA, _make_headers(body, device), body, proxy_url)

    logger.debug(f"[mihoyo] createLoginCaptcha: {data}")
    if data.get("retcode") != 0:
        raise RuntimeError(
            f"发送验证码失败: {data.get('message')} (retcode={data.get('retcode')})"
        )

    return {"device": device}


async def verify_captcha(
    mobile: str,
    captcha: str,
    session: dict,
    proxy_url: str = "",
) -> dict:
    """
    用验证码登录，返回 cookies dict：
      { account_id, mid, stoken, ltoken_v2, cookie_token }
    """
    device = session["device"]

    body = {
        "mobile":      _rsa_encrypt(mobile),
        "captcha":     captcha.strip(),
        "action_type": "login_by_mobile_captcha",
        "area_code":   _rsa_encrypt("+86"),
    }

    data = await _async_post(_URL_LOGIN, _make_headers(body, device), body, proxy_url)

    logger.debug(f"[mihoyo] loginByMobileCaptcha: {data}")
    if data.get("retcode") != 0:
        raise RuntimeError(
            f"验证码错误或已过期: {data.get('message')} (retcode={data.get('retcode')})"
        )

    token_data = data["data"]
    stoken     = token_data["token"]["token"]
    aid        = str(token_data["user_info"]["aid"])
    mid        = token_data["user_info"].get("mid", "")

    cookie_token = await _get_cookie_token(aid, stoken, mid, proxy_url)
    ltoken_v2    = await _get_ltoken_v2(aid, stoken, mid, proxy_url)

    return {
        "account_id":   aid,
        "mid":          mid,
        "stoken":       stoken,
        "ltoken_v2":    ltoken_v2,
        "cookie_token": cookie_token,
    }


async def _get_cookie_token(
    aid: str, stoken: str, mid: str, proxy_url: str = ""
) -> str:
    try:
        data = await _async_get(
            _URL_COOKIE_TOKEN,
            headers={"Cookie": f"stuid={aid};stoken={stoken};mid={mid}"},
            params={"stoken": stoken, "uid": aid, "token_types": "3"},
            proxy_url=proxy_url,
        )
        if data.get("retcode") == 0:
            return data.get("data", {}).get("cookie_token", "")
        logger.warning(f"[mihoyo] 换取 cookie_token 失败: {data}")
    except Exception as e:
        logger.warning(f"[mihoyo] 换取 cookie_token 异常: {e}")
    return ""


async def _get_ltoken_v2(
    aid: str, stoken: str, mid: str, proxy_url: str = ""
) -> str:
    try:
        data = await _async_get(
            _URL_LTOKEN,
            headers={"Cookie": f"stuid={aid};stoken={stoken};mid={mid}"},
            proxy_url=proxy_url,
        )
        if data.get("retcode") == 0:
            ltoken = data.get("data", {}).get("ltoken", "")
            logger.info(f"[mihoyo] 换取 ltoken_v2 成功 (len={len(ltoken)})")
            return ltoken
        logger.warning(f"[mihoyo] 换取 ltoken_v2 失败: {data}")
    except Exception as e:
        logger.warning(f"[mihoyo] 换取 ltoken_v2 异常: {e}")
    return ""
