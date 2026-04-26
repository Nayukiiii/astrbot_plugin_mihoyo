"""
login/fingerprint.py
米游社 device_fp 获取流程

流程：
1. GET  /device-fp/api/getExtList  → 拿到本次需要上报的字段列表
2. POST /device-fp/api/getFp       → 用设备信息换取真实 device_fp
"""

import json
import time
import uuid
import random
import string

import aiohttp
from astrbot.api import logger

try:
    from aiohttp_socks import ProxyConnector
    _SOCKS_OK = True
except ImportError:
    _SOCKS_OK = False

_FP_HOST      = "https://public-data-api.mihoyo.com"
_APP_NAME     = "bbs_cn"
_PLATFORM     = "2"

_URL_EXT_LIST = f"{_FP_HOST}/device-fp/api/getExtList"
_URL_GET_FP   = f"{_FP_HOST}/device-fp/api/getFp"

_ext_list_cache: list[str] | None = None


def make_device_id() -> str:
    """16位小写 hex，模拟 Android ANDROID_ID"""
    return uuid.uuid4().hex[:16]


def make_seed_id() -> str:
    return str(uuid.uuid4())


def make_seed_time() -> str:
    return str(int(time.time() * 1000))


def make_initial_fp() -> str:
    """
    初始 device_fp：10位纯数字
    首位非零，后9位随机数字
    """
    first = str(random.randint(1, 9))
    rest  = "".join(random.choices(string.digits, k=9))
    return first + rest


def _make_connector(proxy_url: str = ""):
    """返回适合代理类型的 connector。SOCKS5 用 ProxyConnector，无代理返回 None。"""
    if not proxy_url:
        return None
    if proxy_url.startswith("socks") and _SOCKS_OK:
        return ProxyConnector.from_url(proxy_url)
    return None


def _request_proxy(proxy_url: str = "") -> str | None:
    """aiohttp 原生 HTTP/HTTPS 代理参数；SOCKS 代理交给 connector。"""
    if proxy_url and not proxy_url.startswith("socks"):
        return proxy_url
    return None


async def _get_ext_list(proxy_url: str = "") -> list[str]:
    global _ext_list_cache
    if _ext_list_cache is not None:
        return _ext_list_cache

    connector = _make_connector(proxy_url)
    timeout   = aiohttp.ClientTimeout(total=15)
    params    = {"platform": _PLATFORM, "app_name": _APP_NAME}

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as s:
            async with s.get(_URL_EXT_LIST, params=params, proxy=_request_proxy(proxy_url)) as resp:
                data = await resp.json(content_type=None)
        ext_list = data.get("data", {}).get("ext_list", [])
        if ext_list:
            _ext_list_cache = ext_list
            logger.debug(f"[mihoyo] getExtList: {ext_list}")
            return ext_list
    except Exception as e:
        logger.warning(f"[mihoyo] getExtList 失败: {e}，使用内置字段列表")

    _ext_list_cache = [
        "androidId", "board", "brand", "cpuType", "deviceType",
        "display", "hardware", "hostname", "manufacturer", "model",
        "osVersion", "productName", "screenSize", "sdkVersion",
        "buildTags", "buildType", "buildUser", "buildTime",
        "romCapacity", "romRemain", "ramCapacity", "ramRemain",
        "networkType", "isRoot", "debugStatus", "proxyStatus",
        "emulatorStatus", "isTablet", "simState",
    ]
    return _ext_list_cache


async def fetch_device_fp(device: dict, proxy_url: str = "") -> str:
    device_id  = device.get("androidId") or make_device_id()
    seed_id    = make_seed_id()
    seed_time  = make_seed_time()
    initial_fp = make_initial_fp()

    ext_list = await _get_ext_list(proxy_url)

    ext_fields_raw = {k: device[k] for k in ext_list if k in device}
    ext_fields_str = json.dumps(ext_fields_raw, separators=(",", ":"), ensure_ascii=False)

    body = {
        "device_id":     device_id,
        "seed_id":       seed_id,
        "seed_time":     seed_time,
        "platform":      _PLATFORM,
        "device_fp":     initial_fp,
        "app_name":      _APP_NAME,
        "bbs_device_id": device_id,
        "ext_fields":    ext_fields_str,
    }

    connector = _make_connector(proxy_url)
    timeout   = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as s:
            async with s.post(
                _URL_GET_FP,
                json=body,
                headers={"Content-Type": "application/json"},
                proxy=_request_proxy(proxy_url),
            ) as resp:
                data = await resp.json(content_type=None)

        fp = data.get("data", {}).get("device_fp", "")
        if fp:
            logger.debug(f"[mihoyo] getFp 成功: {fp}")
            return fp
        logger.warning(f"[mihoyo] getFp 返回空 fp，响应: {data}")
    except Exception as e:
        import traceback
        logger.warning(f"[mihoyo] getFp 失败: {e}\n{traceback.format_exc()}，使用初始 fp")

    return initial_fp
