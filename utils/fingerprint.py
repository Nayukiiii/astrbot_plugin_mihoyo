"""
login/fingerprint.py
米游社 device_fp 获取流程

流程：
1. GET  /device-fp/api/getExtList  → 拿到本次需要上报的字段列表
2. POST /device-fp/api/getFp       → 用设备信息换取真实 device_fp

参考：com.mihoyo.platform.sdk.devicefp.FingerprintService
      com.mihoyo.platform.account.sdk.risk.RiskManager.setup()
"""

import json
import time
import uuid
import random
import string

import aiohttp
from astrbot.api import logger

_FP_HOST      = "https://public-data-api.mihoyo.com"
_APP_NAME     = "bbs_cn"   # porteInfo.getGameBiz()
_PLATFORM     = "2"        # porteInfo.getClientType()

_URL_EXT_LIST = f"{_FP_HOST}/device-fp/api/getExtList"
_URL_GET_FP   = f"{_FP_HOST}/device-fp/api/getFp"

# getExtList 结果缓存，避免每次登录都请求
_ext_list_cache: list[str] | None = None


def make_device_id() -> str:
    """16位小写 hex，模拟 Android ANDROID_ID"""
    return uuid.uuid4().hex[:16]


def make_seed_id() -> str:
    """标准 UUID 格式，含横线"""
    return str(uuid.uuid4())


def make_seed_time() -> str:
    """毫秒时间戳字符串"""
    return str(int(time.time() * 1000))


def make_initial_fp() -> str:
    """
    初始 device_fp：10位纯数字
    对应 DeviceFingerprintSharedPreferences.newDefaultDeviceId() = random(10)
    首位非零，后9位随机数字
    """
    first = str(random.randint(1, 9))
    rest  = "".join(random.choices(string.digits, k=9))
    return first + rest


def _make_proxy_kwargs(proxy_url: str = "") -> dict:
    """返回 aiohttp 请求的 proxy 和 ssl 参数。"""
    if not proxy_url:
        return {}
    import ssl
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    return {"proxy": proxy_url, "ssl": ssl_ctx}


async def _get_ext_list(proxy_url: str = "") -> list[str]:
    """
    GET /device-fp/api/getExtList?platform=2&app_name=bbs_cn
    返回服务器要求上报的 ext_fields 字段名列表。
    结果缓存在进程内，不需要每次登录都请求。
    """
    global _ext_list_cache
    if _ext_list_cache is not None:
        return _ext_list_cache

    proxy_kwargs = _make_proxy_kwargs(proxy_url)
    timeout      = aiohttp.ClientTimeout(total=15)
    params       = {"platform": _PLATFORM, "app_name": _APP_NAME}

    try:
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(_URL_EXT_LIST, params=params, **proxy_kwargs) as resp:
                data = await resp.json(content_type=None)
        ext_list = data.get("data", {}).get("ext_list", [])
        if ext_list:
            _ext_list_cache = ext_list
            logger.debug(f"[mihoyo] getExtList: {ext_list}")
            return ext_list
    except Exception as e:
        logger.warning(f"[mihoyo] getExtList 失败: {e}，使用内置字段列表")

    # 回退：使用从 APK 逆向得到的常见字段子集
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
    """
    用设备信息请求真实 device_fp。

    Args:
        device:    来自 device_pool.pick_device() 的设备信息字典
        proxy_url: SOCKS5 代理地址（可选）

    Returns:
        服务器返回的 device_fp 字符串；失败时返回 make_initial_fp() 的值
    """
    device_id  = device.get("androidId") or make_device_id()
    seed_id    = make_seed_id()
    seed_time  = make_seed_time()
    initial_fp = make_initial_fp()

    # 1. 拿字段列表
    ext_list = await _get_ext_list(proxy_url)

    # 2. 按字段列表过滤设备信息，构造 ext_fields
    ext_fields_raw = {k: device[k] for k in ext_list if k in device}
    ext_fields_str = json.dumps(ext_fields_raw, separators=(",", ":"), ensure_ascii=False)

    # 3. 构造请求体
    body = {
        "device_id":    device_id,
        "seed_id":      seed_id,
        "seed_time":    seed_time,
        "platform":     _PLATFORM,
        "device_fp":    initial_fp,
        "app_name":     _APP_NAME,
        "bbs_device_id": device_id,
        "ext_fields":   ext_fields_str,
    }

    proxy_kwargs = _make_proxy_kwargs(proxy_url)
    timeout      = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.post(
                _URL_GET_FP,
                json=body,
                headers={"Content-Type": "application/json"},
                **proxy_kwargs,
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
