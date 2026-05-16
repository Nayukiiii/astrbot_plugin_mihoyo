"""
utils/slow_hint.py
查询超时追发提示工具

用法：
    async with slow_hint(context, umo, delay=4):
        result = await some_slow_query()
"""

import asyncio
import random
from astrbot.api.event import MessageChain
from astrbot.api import logger

# ── 在这里填你想要的文案 ──────────────────────────────────────────────────────
_SLOW_HINTS = [
    "日本 IP 绕路中... 信号已在海底光缆往返 400 次，再撑几秒秒就好。",  # 填你的文案
    "OCI 正在强连米游社。物理距离摆在那，光子也在努力，马上就到。",
    "OCI → 米游社延迟有点高，撑住",
]
# ─────────────────────────────────────────────────────────────────────────────


class slow_hint:
    """
    async with slow_hint(context, umo, delay=4):
        ...

    超过 delay 秒还没退出，自动追发一条慢提示。
    """

    def __init__(self, context, umo: str, delay: float = 4.0):
        self._context = context
        self._umo = umo
        self._delay = delay
        self._task: asyncio.Task = None

    async def __aenter__(self):
        hints = [h for h in _SLOW_HINTS if h]
        if not hints or not self._context:
            return self

        async def _send_hint():
            await asyncio.sleep(self._delay)
            try:
                msg = random.choice(hints)
                await self._context.send_message(
                    self._umo,
                    MessageChain().message(msg)
                )
            except Exception as e:
                logger.debug(f"[mihoyo] slow_hint 发送失败: {e}")

        self._task = asyncio.create_task(_send_hint())
        return self

    async def __aexit__(self, *_):
        if self._task and not self._task.done():
            self._task.cancel()
