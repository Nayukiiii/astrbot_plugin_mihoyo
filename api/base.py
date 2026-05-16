"""
api/base.py
米游社请求基础工具：DS 算法、Headers、请求封装。

逆向确认（米游社 APK v2.71.1 / libdddd.so / libxxxxxx.so）：

  普通战绩接口 DS salt（bbbbb.a2222 / libxxxx.so）:
    xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs
    对应 API_RECORD 域（api-takumi-record.mihoyo.com）
    client_type=5, DS2 格式（带 b/q 参数），r 为随机整数

  Widget 接口 DS salt（aaaaa.a2222 / libxxxxxx.so）:
    t0qEgfub6cvueAPgR5m9aQWWVciEer7v
    仅用于 widget 路径（jn.l.intercept 拦截器路由规则）:
      /game_record/app/hkrpg/aapi/widget
      /game_record/app/genshin/aapi/widget/v2
      /apihub/app/api/signIn
    client_type=2, DS2 格式（body="" query=""），r 为随机整数
"""

import hashlib
import json
import random
import string
import time
import uuid
from typing import Any, Optional
from urllib.parse import unquote, urlparse

import aiohttp
from astrbot.api import logger

try:
    from aiohttp_socks import ProxyConnector
except ImportError:
    ProxyConnector = None

# ── DS Salts ─────────────────────────────────────────────────────────────────
# 逆向来源：libxxxx.so ANDROID_SALT（bde26df4 / 4200194 掩码解密）
_SALT_RECORD = "xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs"

# 逆向来源：libxxxxxx.so ANDROID_SALT（5efebb5e / 400a0102 掩码解密）
_SALT_WIDGET = "t0qEgfub6cvueAPgR5m9aQWWVciEer7v"

# 账号 SDK（RequestUtils.SALT_PROD，bbs-api 社区接口）
_SALT_BBS = "JwYDpKvLj6MrMqqYU6jTKF17KNO2PXoS"

# ── 设备信息（启动时固定）────────────────────────────────────────────────────
_DEVICE_ID = str(uuid.uuid4())
_DEVICE_FP = "".join(random.choices(string.hexdigits[:16], k=13))

# ── 请求头 ─────────────────────────────────────────────────────────────────────
# 普通战绩接口（client_type=5）
RECORD_HEADERS = {
    "x-rpc-client_type": "5",
    "x-rpc-app_version": "2.11.1",
    "User-Agent":        "okhttp/4.8.0",
    "x-rpc-channel":    "beta",
    "x-rpc-sys_version": "12",
    "x-rpc-device_id":  _DEVICE_ID,
    "x-rpc-device_fp":  _DEVICE_FP,
}

# Widget 接口（client_type=2，逆向自 APK x-rpc-client_type 搜索结果）
WIDGET_HEADERS = {
    "x-rpc-client_type": "2",
    "x-rpc-app_version": "2.71.1",
    "User-Agent":        "okhttp/4.9.3",
    "x-rpc-device_id":  _DEVICE_ID,
    "x-rpc-device_fp":  _DEVICE_FP,
}

# BBS 社区接口（client_type=2）
BBS_HEADERS = {
    "x-rpc-client_type": "2",
    "x-rpc-app_version": "2.71.1",
    "User-Agent":        "okhttp/4.9.3",
    "x-rpc-device_id":  _DEVICE_ID,
    "x-rpc-device_fp":  _DEVICE_FP,
}


# ── DS 计算 ──────────────────────────────────────────────────────────────────

def ds_record(query: str = "", body: str = "") -> str:
    """
    普通战绩接口 DS（bbbbb.a2222 算法）。
    salt=xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs, r 为随机整数 100001-200000。
    """
    t = int(time.time())
    r = random.randint(100001, 200000)
    h = hashlib.md5(
        f"salt={_SALT_RECORD}&t={t}&r={r}&b={body}&q={query}".encode()
    ).hexdigest()
    return f"{t},{r},{h}"


def ds_widget(query: str = "", body: str = "") -> str:
    """
    Widget 接口 DS（aaaaa.a2222 算法）。
    salt=t0qEgfub6cvueAPgR5m9aQWWVciEer7v, r 为随机整数 100001-200000。
    Widget 为 GET 无参请求，body="" query="" 直接传空。
    """
    t = int(time.time())
    r = random.randint(100001, 200000)
    h = hashlib.md5(
        f"salt={_SALT_WIDGET}&t={t}&r={r}&b={body}&q={query}".encode()
    ).hexdigest()
    return f"{t},{r},{h}"


def ds_bbs() -> str:
    """BBS 社区接口 DS（SALT_PROD，r 为字母数字字符串）。"""
    t = int(time.time())
    r = "".join(random.choices(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=6
    ))
    h = hashlib.md5(f"salt={_SALT_BBS}&t={t}&r={r}".encode()).hexdigest()
    return f"{t},{r},{h}"


def sorted_query(params: dict) -> str:
    """将 params dict 转为按字母升序排列的 query string（DS 计算用）。"""
    return "&".join(f"{k}={v}" for k, v in sorted(params.items()))


# ── 网络工具 ─────────────────────────────────────────────────────────────────

def make_connector(proxy_url: str = ""):
    """创建 SOCKS5 ProxyConnector，无代理返回 None。"""
    if not proxy_url or not ProxyConnector:
        return None
    try:
        p = urlparse(proxy_url)
        return ProxyConnector(
            host=p.hostname,
            port=p.port or 1080,
            username=unquote(p.username) if p.username else None,
            password=unquote(p.password) if p.password else None,
            rdns=True,
            family=2,
        )
    except Exception as e:
        logger.warning(f"[mihoyo][api] proxy_url 解析失败，降级直连: {e}")
        return None


# ── 请求封装 ─────────────────────────────────────────────────────────────────

async def mys_get(
    url: str,
    params: dict,
    cookie: str,
    extra_headers: Optional[dict] = None,
    proxy_url: str = "",
    challenge: str = "",
    session: Any = None,
) -> dict:
    """
    发送 GET 请求到米游社战绩接口，自动计算普通 DS（xV8v4Qu5...）。
    params 按字母排序后用于 DS 计算和请求 URL。
    """
    query = sorted_query(params)
    headers = {
        **RECORD_HEADERS,
        "Cookie": cookie,
        "DS":     ds_record(query=query),
    }
    if challenge:
        headers["x-rpc-challenge"] = challenge
    if extra_headers:
        headers.update(extra_headers)

    timeout = aiohttp.ClientTimeout(total=30)
    try:
        if session is not None:
            from http.cookies import SimpleCookie
            import yarl
            sc = SimpleCookie()
            sc.load(cookie)
            for key, morsel in sc.items():
                session.cookie_jar.update_cookies(
                    {key: morsel.value},
                    response_url=yarl.URL("https://api-takumi-record.mihoyo.com"),
                )
            headers_no_cookie = {k: v for k, v in headers.items() if k != "Cookie"}
            async with session.get(
                f"{url}?{query}", headers=headers_no_cookie, timeout=timeout
            ) as resp:
                raw = await resp.text()
        else:
            connector = make_connector(proxy_url)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as sess:
                async with sess.get(f"{url}?{query}", headers=headers) as resp:
                    raw = await resp.text()

        data = json.loads(raw)
        retcode = data.get("retcode", -1)
        if retcode not in (0, 1034, 5003, 10035, 10041):
            logger.warning(
                f"[mihoyo][api] GET {url} retcode={retcode} msg={data.get('message')}"
            )
        return data
    except Exception as e:
        logger.error(f"[mihoyo][api] GET {url} 异常: {e}")
        raise


async def mys_widget_get(
    url: str,
    cookie: str,
    proxy_url: str = "",
) -> dict:
    """
    发送 GET 请求到 Widget 接口，使用 Widget 专用 DS salt 和 headers。

    逆向确认：
    - 路径在 jn.l.intercept 拦截器白名单中（/game_record/app/hkrpg/aapi/widget 等）
    - 使用 aaaaa.a2222(body="", query="") 生成 DS
    - client_type=2, salt=t0qEgfub6cvueAPgR5m9aQWWVciEer7v
    - 无需 role_id/server 参数，从 cookie 中的 stoken 推断账号
    - 不触发极验（10041），是便笺接口的无验证替代路径
    """
    headers = {
        **WIDGET_HEADERS,
        "Cookie": cookie,
        "DS":     ds_widget(),
    }
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        connector = make_connector(proxy_url)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as sess:
            async with sess.get(url, headers=headers) as resp:
                raw = await resp.text()
        data = json.loads(raw)
        retcode = data.get("retcode", -1)
        if retcode != 0:
            logger.warning(
                f"[mihoyo][api] widget GET {url} retcode={retcode} msg={data.get('message')}"
            )
        return data
    except Exception as e:
        logger.error(f"[mihoyo][api] widget GET {url} 异常: {e}")
        raise


async def mys_post(
    url: str,
    body: dict,
    cookie: str,
    extra_headers: Optional[dict] = None,
    proxy_url: str = "",
) -> dict:
    """发送 POST 请求到米游社接口，自动计算普通 DS。"""
    body_str = json.dumps(body, separators=(",", ":"), sort_keys=True)
    headers = {
        **RECORD_HEADERS,
        "Cookie":       cookie,
        "DS":           ds_record(body=body_str),
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    connector = make_connector(proxy_url)
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as sess:
            async with sess.post(url, headers=headers, data=body_str) as resp:
                raw = await resp.text()
        return json.loads(raw)
    except Exception as e:
        logger.error(f"[mihoyo][api] POST {url} 异常: {e}")
        raise


# ── 极验相关 ─────────────────────────────────────────────────────────────────

GEETEST_RETCODES = {1034, 5003, 10035, 10041}


def is_geetest_triggered(data: dict) -> bool:
    return data.get("retcode") in GEETEST_RETCODES
