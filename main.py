"""
main.py
插件入口，注册所有指令。
"""

from typing import Optional

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import AstrBotConfig, logger

from .db.database import init_db
from .commands.account import cmd_login, cmd_verify, cmd_unbind, cmd_account_info, handle_private_message
from .commands.notes import (
    cmd_genshin_notes, cmd_genshin_checkin,
    cmd_starrail_notes, cmd_starrail_checkin,
)
from .commands.gacha import cmd_gacha, cmd_gacha_authkey, get_cached_authkey
from .commands.abyss import (
    cmd_spiral_abyss,
    cmd_forgotten_hall,
    cmd_pure_fiction,
    cmd_apocalyptic_shadow,
)


@register(
    "astrbot_plugin_mihoyo",
    "Nayuki",
    "原神 & 崩坏：星穹铁道 查询插件",
    "0.3.0",
)
class MihoyoPlugin(Star):

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}

        data_dir = str(StarTools.get_data_dir("astrbot_plugin_mihoyo"))
        init_db(data_dir)

        proxy   = self.config.get("proxy", {})
        captcha = self.config.get("captcha", {})
        login   = self.config.get("login", {})
        gacha   = self.config.get("gacha", {})

        self._login_proxy      = str(proxy.get("login_proxy_url", ""))
        self._geetest_proxy    = str(proxy.get("geetest_proxy_url", ""))
        self._captcha_provider = str(captcha.get("provider", "ttocr"))
        self._ttocr_key        = str(captcha.get("ttocr_appkey", ""))
        self._capsolver_key    = str(captcha.get("capsolver_apikey", ""))
        self._geetest_server   = str(captcha.get("geetest_server_url", "https://geetest.utautai.org"))
        self._max_login_wait   = int(login.get("max_wait", 300))
        self._gacha_sync_limit = int(gacha.get("sync_limit", 0))

        logger.info(
            f"[mihoyo] 插件已加载 v0.3.0 | "
            f"captcha={self._captcha_provider} | "
            f"login_proxy={'已配置' if self._login_proxy else '未配置'} | "
            f"geetest_server={self._geetest_server}"
        )

    @property
    def _geetest_kwargs(self) -> dict:
        return {
            "captcha_provider":   self._captcha_provider,
            "ttocr_key":          self._ttocr_key,
            "capsolver_key":      self._capsolver_key,
            "geetest_server_url": self._geetest_server,
            "proxy_url":          self._geetest_proxy,
            "login_proxy_url":    self._login_proxy,
            "context":            self.context,
        }

    # ── /米 ──────────────────────────────────────────────────────────────────

    @filter.command("米")
    async def handle_mi(self, event: AstrMessageEvent):
        """/米 登录 | 解绑 | 账号"""
        args = self._args(event, prefix="米")
        if not args:
            yield event.plain_result(
                "用法：\n/米 登录 — 发送验证码\n/米 验证 — 完成绑定\n/米 解绑\n/米 账号"
            )
            return
        sub = args[0]
        if sub in ("登录", "login"):
            async for r in cmd_login(event, args=args[1:], proxy_url=self._login_proxy,
                                     max_wait=self._max_login_wait, context=self.context):
                yield r
        elif sub in ("验证", "verify"):
            async for r in cmd_verify(event, args=args[1:], proxy_url=self._login_proxy,
                                      context=self.context):
                yield r
        elif sub in ("解绑", "unbind"):
            async for r in cmd_unbind(event):
                yield r
        elif sub in ("账号", "account", "info"):
            async for r in cmd_account_info(event):
                yield r
        else:
            yield event.plain_result(f"未知子命令「{sub}」\n用法：/米 登录 | 解绑 | 账号")

    # ── /原 ──────────────────────────────────────────────────────────────────

    @filter.command("原")
    async def handle_gs(self, event: AstrMessageEvent):
        """/原 便笺 | 签到 | 深渊 [上期] | 抽卡 <池子>"""
        args = self._args(event, prefix="原")
        if not args:
            yield event.plain_result(self._gs_help())
            return
        sub = args[0]
        gk  = self._geetest_kwargs

        if sub in ("便笺", "note"):
            async for r in cmd_genshin_notes(event, unified_msg_origin=event.unified_msg_origin, **gk):
                yield r
        elif sub in ("签到", "checkin"):
            async for r in cmd_genshin_checkin(event, unified_msg_origin=event.unified_msg_origin, **gk):
                yield r
        elif sub in ("深渊", "abyss"):
            previous = len(args) > 1 and args[1] == "上期"
            async for r in cmd_spiral_abyss(event, previous=previous,
                                            unified_msg_origin=event.unified_msg_origin, **gk):
                yield r
        elif sub in ("抽卡", "gacha"):
            if len(args) < 2:
                yield event.plain_result("请指定池子：/原 抽卡 角色 | 武器 | 常驻 | 新手")
                return
            if args[1] in ("链接", "url") and len(args) > 2:
                async for r in cmd_gacha_authkey(event, "genshin", args[2]):
                    yield r
                return
            authkey = get_cached_authkey(str(event.get_sender_id()), "genshin")
            async for r in cmd_gacha(event, "genshin", args[1], authkey=authkey,
                                     max_pages=self._gacha_sync_limit):
                yield r
        elif sub in ("角色", "char"):
            yield event.plain_result("🚧 展柜功能开发中")
        else:
            yield event.plain_result(f"未知子命令「{sub}」\n{self._gs_help()}")

    # ── /崩 ──────────────────────────────────────────────────────────────────

    @filter.command("崩")
    async def handle_sr(self, event: AstrMessageEvent):
        """/崩 便笺 | 签到 | 忘却 [上期] | 虚构 [上期] | 末日 [上期] | 抽卡 <池子>"""
        args = self._args(event, prefix="崩")
        if not args:
            yield event.plain_result(self._sr_help())
            return
        sub = args[0]
        gk  = self._geetest_kwargs

        if sub in ("便笺", "note"):
            async for r in cmd_starrail_notes(event, unified_msg_origin=event.unified_msg_origin, **gk):
                yield r
        elif sub in ("签到", "checkin"):
            async for r in cmd_starrail_checkin(event, unified_msg_origin=event.unified_msg_origin, **gk):
                yield r
        elif sub in ("忘却",):
            previous = len(args) > 1 and args[1] == "上期"
            async for r in cmd_forgotten_hall(event, previous=previous,
                                              unified_msg_origin=event.unified_msg_origin, **gk):
                yield r
        elif sub in ("虚构",):
            previous = len(args) > 1 and args[1] == "上期"
            async for r in cmd_pure_fiction(event, previous=previous,
                                            unified_msg_origin=event.unified_msg_origin, **gk):
                yield r
        elif sub in ("末日", "差分"):
            previous = len(args) > 1 and args[1] == "上期"
            async for r in cmd_apocalyptic_shadow(event, previous=previous,
                                                  unified_msg_origin=event.unified_msg_origin, **gk):
                yield r
        elif sub in ("抽卡", "gacha", "warp"):
            if len(args) < 2:
                yield event.plain_result("请指定池子：/崩 抽卡 角色 | 光锥 | 常驻 | 新手")
                return
            if args[1] in ("链接", "url") and len(args) > 2:
                async for r in cmd_gacha_authkey(event, "starrail", args[2]):
                    yield r
                return
            authkey = get_cached_authkey(str(event.get_sender_id()), "starrail")
            async for r in cmd_gacha(event, "starrail", args[1], authkey=authkey,
                                     max_pages=self._gacha_sync_limit):
                yield r
        elif sub in ("角色", "char"):
            yield event.plain_result("🚧 展柜功能开发中")
        else:
            yield event.plain_result(f"未知子命令「{sub}」\n{self._sr_help()}")

    # ── 私聊监听 ─────────────────────────────────────────────────────────────

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def handle_private_msg(self, event: AstrMessageEvent):
        await handle_private_message(
            event, proxy_url=self._login_proxy,
            max_wait=self._max_login_wait, context=self.context,
        )

    # ── 工具方法 ─────────────────────────────────────────────────────────────

    def _args(self, event: AstrMessageEvent, prefix: str) -> list[str]:
        raw = event.message_str
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        raw = raw.strip()
        for p in (f"/{prefix}", prefix):
            if raw.startswith(p):
                raw = raw[len(p):].strip()
                break
        return [x for x in raw.split() if x]

    def _gs_help(self) -> str:
        return (
            "原神指令：\n"
            "/原 便笺 — 树脂/委托/宝钱\n"
            "/原 签到\n"
            "/原 深渊 [上期]\n"
            "/原 抽卡 角色|武器|常驻|新手\n"
            "/原 抽卡 链接 <URL>"
        )

    def _sr_help(self) -> str:
        return (
            "崩铁指令：\n"
            "/崩 便笺 — 开拓力/每日/模拟宇宙\n"
            "/崩 签到\n"
            "/崩 忘却 [上期]\n"
            "/崩 虚构 [上期]\n"
            "/崩 末日 [上期]\n"
            "/崩 抽卡 角色|光锥|常驻|新手\n"
            "/崩 抽卡 链接 <URL>"
        )
