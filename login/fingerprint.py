"""
login/fingerprint.py
米游社 device_fp 获取流程

流程：
1. GET  /device-fp/api/getExtList  → 拿到本次需要上报的字段列表
2. POST /device-fp/api/getFp       → 用设备信息换取真实 device_fp
"""

import asyncio
import json
import subprocess
import time
import uuid
import random
import string

from astrbot.api import logger

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


def _curl_json(method: str, url: str, body: dict = None, proxy_url: str = "", timeout: int = 20) -> dict:
    cmd = ["curl", "-sS", "--connect-timeout", "12", "--max-time", str(timeout)]
    if proxy_url:
        cmd += ["--proxy", proxy_url]
    if method.upper() == "POST" and body is not None:
        cmd += ["-X", "POST", "-H", "Content-Type: application/json",
                "-d", json.dumps(body, separators=(",", ":"), ensure_ascii=False)]
    cmd.append(url)
    # 简单重试 3 次，绕过 DataImpulse 偶发 TCP 失败
    last = ""
    for i in range(3):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        if r.returncode == 0 and r.stdout:
            return json.loads(r.stdout)
        last = f"exit {r.returncode}: {r.stderr[:100]}"
        time.sleep(1 + i)
    raise RuntimeError(last)


async def _get_ext_list(proxy_url: str = "") -> list[str]:
    global _ext_list_cache
    if _ext_list_cache is not None:
        return _ext_list_cache

    url = f"{_URL_EXT_LIST}?platform={_PLATFORM}&app_name={_APP_NAME}"
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, _curl_json, "GET", url, None, proxy_url
        )
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

    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, _curl_json, "POST", _URL_GET_FP, body, proxy_url
        )
        fp = data.get("data", {}).get("device_fp", "")
        if fp:
            logger.debug(f"[mihoyo] getFp 成功: {fp}")
            return fp
        logger.warning(f"[mihoyo] getFp 返回空 fp，响应: {data}")
    except Exception as e:
        logger.warning(f"[mihoyo] getFp 失败: {e}，使用初始 fp")

    return initial_fp
