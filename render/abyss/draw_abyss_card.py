"""
render/abyss/draw_abyss_card.py
深渊 / 忘却之庭 / 虚构叙事 / 差分宇宙 PIL 渲染。

改编自 StarRailUID（baiqwerdvd/StarRailUID），GPL-3.0 License。
原始作者：baiqwerdvd 等贡献者。
本实现移除了 gsuid_core 依赖，改为纯 PIL 实现。

资源文件首次使用时从 StarRailUID 仓库静默下载。
"""

import asyncio
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw
from astrbot.api import logger

from ..starrailuid_assets import first_existing, vendor_texture
from ..base_card import (
    WHITE, GRAY, BLACK, convert_img,
    SR_PURPLE, SR_ACCENT, SR_BG_TOP, SR_BG_BOT,
    GS_GOLD, GS_BG_TOP, GS_BG_BOT,
    create_gradient_bg, draw_rounded_rect, draw_progress_bar,
)
from ..fonts.starrail_fonts import get_font

# ── 资源路径 ──────────────────────────────────────────────────────────────────
_TEXTURE_DIR = Path(__file__).parent / "texture2D"
_TEXTURE_DIR.mkdir(exist_ok=True)
_VENDOR_TEXTURE_DIR = vendor_texture("starrailuid_abyss_boss")

_SR_ABYSS_BASE = (
    "https://raw.githubusercontent.com/baiqwerdvd/StarRailUID/"
    "master/StarRailUID/starrailuid_abyss_boss/texture2D/"
)
_SR_REQUIRED = ["bg.jpg", "floor_bg.png", "star.png", "star_gray.png"]


async def _ensure_sr_assets():
    if _VENDOR_TEXTURE_DIR.exists():
        return
    missing = [f for f in _SR_REQUIRED if not (_TEXTURE_DIR / f).exists()]
    if not missing:
        return
    logger.info(f"[render/abyss] 下载 SR 资源: {missing}")
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        ) as sess:
            for fname in missing:
                url = _SR_ABYSS_BASE + fname
                try:
                    async with sess.get(url) as resp:
                        if resp.status == 200:
                            (_TEXTURE_DIR / fname).write_bytes(await resp.read())
                            logger.info(f"[render/abyss] 下载成功: {fname}")
                        else:
                            logger.warning(f"[render/abyss] 下载失败 {fname}: {resp.status}")
                except Exception as e:
                    logger.warning(f"[render/abyss] 下载失败 {fname}: {e}")
    except Exception as e:
        logger.warning(f"[render/abyss] 资源下载异常: {e}")


def _load(name: str, fallback_size=(900, 100)):
    p = first_existing(_VENDOR_TEXTURE_DIR / name, _TEXTURE_DIR / name)
    if p and p.exists():
        try:
            return Image.open(p).convert("RGBA")
        except Exception:
            pass
    return Image.new("RGBA", fallback_size, (40, 40, 60, 200))


def _fmt_time(seconds: int) -> str:
    if seconds <= 0:
        return "已满"
    h, m = divmod(seconds // 60, 60)
    return f"{h}h{m}m" if h else f"{m}分钟"


# ── 崩铁终局挑战通用渲染 ───────────────────────────────────────────────────────

def _draw_endgame(
    data, uid: str, title: str, previous: bool,
    accent: tuple, bg_top: tuple, bg_bot: tuple,
) -> Image.Image:
    """通用终局挑战卡片（忘却/虚构/差分）。"""
    period  = "上期" if previous else "本期"
    floors  = getattr(data, "floors", [])
    n_floors = len(floors)

    W       = 900
    H_HEAD  = 280
    H_FLOOR = 220
    H       = H_HEAD + H_FLOOR * n_floors + 40

    img = create_gradient_bg(W, H, bg_top, bg_bot)
    draw = ImageDraw.Draw(img)

    f_big   = get_font(42)
    f_med   = get_font(28)
    f_small = get_font(22)
    f_tiny  = get_font(18)

    # 尝试背景图
    bg_path = first_existing(_VENDOR_TEXTURE_DIR / "bg.jpg", _TEXTURE_DIR / "bg.jpg")
    if bg_path and bg_path.exists():
        try:
            bg = Image.open(bg_path).convert("RGB").resize((W, H))
            img.paste(bg, (0, 0))
            draw = ImageDraw.Draw(img)
        except Exception:
            pass

    # 标题区半透明层
    overlay = Image.new("RGBA", (W, H_HEAD), (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)
    draw_rounded_rect(ov, (0, 0, W, H_HEAD), radius=0, fill=(10, 10, 20, 160))
    img_rgba = img.convert("RGBA")
    img_rgba.paste(overlay, (0, 0), overlay)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # 标题
    draw.text((W // 2, 50), f"{title}  {period}", font=f_big,
              fill=tuple(accent), anchor="mm")
    draw.text((W // 2, 100), f"UID {uid}", font=f_small, fill=GRAY, anchor="mm")

    # 总体数据
    stars    = getattr(data, "total_stars", 0)
    max_fl   = getattr(data, "max_floor", "—")
    battles  = getattr(data, "battle_num", 0)
    has_data = getattr(data, "has_data", False)

    if not has_data:
        draw.text((W // 2, H // 2), f"本期暂无 {title} 数据", font=f_med,
                  fill=GRAY, anchor="mm")
        return img

    draw.text((180, 160), f"最深：{max_fl}", font=f_med, fill=WHITE)
    draw.text((180, 200), f"出战：{battles} 次", font=f_small, fill=GRAY)
    draw.text((W - 180, 160), f"★ {stars}", font=f_big, fill=(244, 208, 63), anchor="ra")
    draw.line([(40, 260), (W - 40, 260)], fill=(80, 80, 100), width=1)

    # 楼层
    star_img      = _load("star.png", (30, 30)).resize((28, 28))
    star_gray_img = _load("star_gray.png", (30, 30)).resize((28, 28))

    y = H_HEAD + 10
    for floor in floors:
        # 楼层背景
        fl_overlay = Image.new("RGBA", (W - 80, H_FLOOR - 20), (0, 0, 0, 0))
        fl_ov = ImageDraw.Draw(fl_overlay)
        draw_rounded_rect(fl_ov, (0, 0, W - 80, H_FLOOR - 20), radius=12,
                          fill=(25, 25, 40, 210))
        img_rgba = img.convert("RGBA")
        img_rgba.paste(fl_overlay, (40, y), fl_overlay)
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)

        # 楼层名 + 星星
        floor_name = getattr(floor, "name", "—")
        fl_stars   = getattr(floor, "stars", 0)
        draw.text((60, y + 16), floor_name, font=f_med, fill=WHITE)
        for si in range(3):
            si_img = star_img if si < fl_stars else star_gray_img
            img.paste(si_img, (W - 160 + si * 36, y + 12), si_img)

        # 节点角色
        for ni, node_attr in enumerate(["node_1", "node_2"]):
            node = getattr(floor, node_attr, None)
            if node is None:
                continue
            chars = getattr(node, "characters", [])
            label = f"节点{ni + 1}"
            x_start = 60 + ni * ((W - 160) // 2)
            draw.text((x_start, y + 58), label, font=f_tiny, fill=GRAY)
            names = "、".join(c.name for c in chars[:4]) if chars else "—"
            draw.text((x_start, y + 80), names, font=f_small, fill=WHITE)

        y += H_FLOOR

    return img


# ── 公开渲染函数 ───────────────────────────────────────────────────────────────

async def render_forgotten_hall(data, uid: str, previous: bool = False) -> bytes:
    await _ensure_sr_assets()
    img = _draw_endgame(
        data, uid, "忘却之庭", previous,
        accent=SR_ACCENT, bg_top=SR_BG_TOP, bg_bot=SR_BG_BOT,
    )
    return convert_img(img)


async def render_pure_fiction(data, uid: str, previous: bool = False) -> bytes:
    await _ensure_sr_assets()
    img = _draw_endgame(
        data, uid, "虚构叙事", previous,
        accent=(244, 114, 182), bg_top=(20, 10, 30), bg_bot=(60, 20, 80),
    )
    return convert_img(img)


async def render_apocalyptic_shadow(data, uid: str, previous: bool = False) -> bytes:
    await _ensure_sr_assets()
    img = _draw_endgame(
        data, uid, "差分宇宙", previous,
        accent=(96, 165, 250), bg_top=(10, 20, 40), bg_bot=(20, 40, 80),
    )
    return convert_img(img)


async def render_spiral_abyss(data, uid: str, previous: bool = False) -> bytes:
    """原神深境螺旋。"""
    period   = "上期" if previous else "本期"
    W, H_BAS = 900, 300
    floors   = [f for f in getattr(data, "floors", []) if getattr(f, "floor", 0) >= 9]
    H        = H_BAS + 160 * len(floors) + 40

    img = create_gradient_bg(W, H, GS_BG_TOP, GS_BG_BOT)
    draw = ImageDraw.Draw(img)

    f_big   = get_font(42)
    f_med   = get_font(28)
    f_small = get_font(22)
    f_tiny  = get_font(18)

    draw.text((W // 2, 50), f"深境螺旋  {period}", font=f_big, fill=GS_GOLD, anchor="mm")
    draw.text((W // 2, 100), f"UID {uid}", font=f_small, fill=GRAY, anchor="mm")

    total_stars = getattr(data, "total_stars", 0)
    max_floor   = getattr(data, "max_floor", "—")
    draw.text((180, 160), f"最深：{max_floor}", font=f_med, fill=WHITE)
    draw.text((W - 180, 160), f"★ {total_stars}/36", font=f_big,
              fill=(244, 208, 63), anchor="ra")
    draw.line([(40, 220), (W - 40, 220)], fill=(80, 80, 60), width=1)

    y = H_BAS
    for floor in reversed(floors):
        for chamber in reversed(getattr(floor, "chambers", [])):
            draw.text((60, y + 10),
                      f"第 {floor.floor}-{chamber.chamber} 间",
                      font=f_med, fill=WHITE)
            fl_stars = getattr(chamber, "stars", 0)
            star_str = "★" * fl_stars + "☆" * (3 - fl_stars)
            draw.text((W - 60, y + 10), star_str, font=f_med,
                      fill=(244, 208, 63), anchor="ra")

            for hi, half_attr in enumerate(["first_half", "second_half"]):
                half = getattr(chamber, half_attr, None)
                if half:
                    label = "上半" if hi == 0 else "下半"
                    names = "、".join(
                        c.name for c in getattr(half, "characters", [])
                    ) or "—"
                    draw.text((60, y + 46 + hi * 26), f"{label}：{names}",
                              font=f_small, fill=GRAY)
            y += 100

    return convert_img(img)
