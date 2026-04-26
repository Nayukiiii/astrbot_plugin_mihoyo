"""
render/notes/draw_notes_card.py
崩铁 / 原神 便笺卡片 PIL 渲染。

资源文件（texture2D/）首次使用时从 StarRailUID 仓库静默下载。
未下载时使用纯程序绘制的简化版卡片，功能完整。

资源来源：https://github.com/baiqwerdvd/StarRailUID
协议：GPL-3.0 License
"""

import asyncio
import io
from pathlib import Path
from typing import Optional

import aiohttp
from PIL import Image, ImageDraw
from astrbot.api import logger

from ..starrailuid_assets import first_existing, vendor_texture
from ..base_card import (
    WHITE, GRAY, convert_img,
    SR_PURPLE, SR_ACCENT, SR_BG_TOP, SR_BG_BOT,
    GS_GOLD, GS_BG_TOP, GS_BG_BOT,
    create_gradient_bg, draw_rounded_rect, draw_progress_bar,
    draw_text_shadow,
)
from ..fonts.starrail_fonts import get_font

_TEXTURE_DIR = Path(__file__).parent / "texture2D"
_TEXTURE_DIR.mkdir(exist_ok=True)
_VENDOR_NOTE_DIR = vendor_texture("starrailuid_note", "texture2d")
_VENDOR_STAMINA_DIR = vendor_texture("starrailuid_stamina")

# StarRailUID 资源 CDN（便笺模块）
_ASSET_BASE = (
    "https://raw.githubusercontent.com/baiqwerdvd/StarRailUID/"
    "master/StarRailUID/starrailuid_note/texture2D/"
)
_REQUIRED_ASSETS = ["bg.jpg", "head.png"]


async def _ensure_assets():
    if _VENDOR_NOTE_DIR.exists() or _VENDOR_STAMINA_DIR.exists():
        return
    """静默下载缺失的 texture2D 资源（首次使用时调用）。"""
    missing = [f for f in _REQUIRED_ASSETS if not (_TEXTURE_DIR / f).exists()]
    if not missing:
        return
    logger.info(f"[render/notes] 下载缺失资源: {missing}")
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        ) as sess:
            for fname in missing:
                url = _ASSET_BASE + fname
                try:
                    async with sess.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            (_TEXTURE_DIR / fname).write_bytes(data)
                            logger.info(f"[render/notes] 下载成功: {fname}")
                        else:
                            logger.warning(f"[render/notes] 下载失败 {fname}: HTTP {resp.status}")
                except Exception as e:
                    logger.warning(f"[render/notes] 下载失败 {fname}: {e}")
    except Exception as e:
        logger.warning(f"[render/notes] 资源下载异常: {e}")


def _fmt_time(seconds: int) -> str:
    if seconds <= 0:
        return "已满"
    h, m = divmod(seconds // 60, 60)
    if h:
        return f"{h}小时{m}分钟"
    return f"{m}分钟"


def _seconds(value) -> int:
    if value is None:
        return 0
    if hasattr(value, "total_seconds"):
        return int(value.total_seconds())
    return int(value)


def _hhmmss(seconds: int) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _hhmm_cn(seconds: int) -> str:
    m, _ = divmod(max(0, int(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}小时{m:02d}分"


def _load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


async def _render_starrail_notes_starrailuid(notes, uid: str, nickname: str = "") -> bytes:
    """StarRailUID 风格的崩铁便笺卡。"""
    note_bg_path = _VENDOR_STAMINA_DIR / "note_bg.png"
    travel_bg_path = _VENDOR_STAMINA_DIR / "note_travel_bg.png"
    ring_path = _VENDOR_STAMINA_DIR / "ring.apng"
    if not note_bg_path.exists():
        raise FileNotFoundError(f"missing StarRailUID note asset: {note_bg_path}")

    img = _load_rgba(note_bg_path)
    draw = ImageDraw.Draw(img)

    f_22 = get_font(22)
    f_18 = get_font(18)
    f_20 = get_font(20)
    f_24 = get_font(24)
    f_26 = get_font(26)
    f_36 = get_font(36)
    f_50 = get_font(50)

    first_color = (29, 29, 29)
    second_color = (98, 98, 98)
    white_color = (255, 255, 255)
    red_color = (235, 61, 75)

    stamina = int(getattr(notes, "current_stamina", 0) or 0)
    max_stamina = int(getattr(notes, "max_stamina", 0) or 0)
    stamina_percent = stamina / max_stamina if max_stamina else 0
    recover_sec = _seconds(getattr(notes, "stamina_recover_time", 0))
    stamina_color = red_color if stamina_percent >= 0.8 else second_color

    if ring_path.exists():
        try:
            ring = Image.open(ring_path)
            percent = min(89, max(0, round(stamina_percent * 89)))
            ring.seek(percent)
            ring = ring.convert("RGBA")
            img.paste(ring, (0, 5), ring)
        except Exception as e:
            logger.warning(f"[render/notes] StarRailUID ring 加载失败: {e}")

    draw.text((350, 139), nickname or "开拓者", font=f_36, fill=white_color, anchor="mm")
    draw.text((350, 190), "崩坏：星穹铁道", font=f_24, fill=white_color, anchor="mm")
    draw.text((350, 450), f"{stamina}/{max_stamina}", font=f_50, fill=first_color, anchor="mm")
    draw.text((350, 490), f"还剩{_hhmm_cn(recover_sec)}", font=f_24, fill=stamina_color, anchor="mm")
    draw.text((350, 663), f"UID{uid}", font=f_26, fill=first_color, anchor="mm")

    reserve = int(getattr(notes, "current_reserve_stamina", 0) or 0)
    if reserve:
        draw.text((350, 535), f"备用开拓力 {reserve}", font=f_22, fill=second_color, anchor="mm")

    score_items = [
        ("每日实训", f"{getattr(notes, 'current_train_score', 0)}/{getattr(notes, 'max_train_score', 500)}"),
        ("模拟宇宙", f"{getattr(notes, 'current_rogue_score', 0)}/{getattr(notes, 'max_rogue_score', 14000)}"),
    ]
    if getattr(notes, "rogue_tourn_weekly_unlocked", False):
        score_items.append(
            ("差分宇宙", f"{getattr(notes, 'rogue_tourn_weekly_cur', 0)}/{getattr(notes, 'rogue_tourn_weekly_max', 0)}")
        )
    score_xs = (175, 350, 525) if len(score_items) >= 3 else (260, 440)
    for index, (label, value) in enumerate(score_items):
        x = score_xs[index]
        draw.text((x, 694), label, font=f_18, fill=second_color, anchor="mm")
        draw.text((x, 720), value, font=f_20, fill=first_color, anchor="mm")

    expeditions = list(getattr(notes, "expeditions", None) or [])
    accepted = int(getattr(notes, "accepted_expedition_num", len(expeditions)) or 0)
    total = int(getattr(notes, "total_expedition_num", 4) or 4)
    draw.text((610, 755), f"{accepted}/{total}", font=f_24, fill=first_color, anchor="rm")

    for index in range(4):
        y = 790 + index * 80
        if travel_bg_path.exists():
            travel_bg = _load_rgba(travel_bg_path)
            img.paste(travel_bg, (0, y), travel_bg)
        exp = expeditions[index] if index < len(expeditions) else None
        if exp is None:
            draw.text((120, y + 40), "等待加入探索队列...", font=f_22, fill=white_color, anchor="lm")
            continue
        name = getattr(exp, "name", "委托派遣")
        remaining = _seconds(getattr(exp, "remaining_time", 0))
        finished = bool(getattr(exp, "finished", False))
        status = "待收取" if finished or remaining <= 0 else _hhmmss(remaining)
        draw.text((120, y + 40), name, font=f_22, fill=white_color, anchor="lm")
        draw.text((405, y + 40), status, font=f_22, fill=white_color, anchor="mm")

    return convert_img(img.convert("RGB"))


# ── 崩铁便笺卡片 ───────────────────────────────────────────────────────────────

async def render_starrail_notes(
    notes,
    uid: str,
    nickname: str = "",
) -> bytes:
    """崩铁便笺 → PNG bytes。"""
    return await _render_starrail_notes_starrailuid(notes, uid, nickname)

    await _ensure_assets()

    W, H = 560, 480
    img = create_gradient_bg(W, H, SR_BG_TOP, SR_BG_BOT)
    draw = ImageDraw.Draw(img)

    # 尝试加载背景
    bg_path = first_existing(
        _VENDOR_STAMINA_DIR / "note_bg.png",
        _VENDOR_NOTE_DIR / "monthly_bg.png",
        _TEXTURE_DIR / "bg.jpg",
    )
    if bg_path and bg_path.exists():
        try:
            bg = Image.open(bg_path).convert("RGB").resize((W, H))
            img.paste(bg, (0, 0))
            draw = ImageDraw.Draw(img)
        except Exception:
            pass

    # 卡片主体（半透明层）
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    draw_rounded_rect(ov_draw, (16, 16, W - 16, H - 16), radius=16,
                      fill=(20, 20, 35, 200))
    img = img.convert("RGBA")
    img.paste(overlay, (0, 0), overlay)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    f_big   = get_font(38)
    f_med   = get_font(22)
    f_small = get_font(18)
    f_title = get_font(28)

    # ── 标题栏 ────────────────────────────────────────────────────────────────
    draw.text((32, 28), "崩坏：星穹铁道", font=f_title, fill=SR_ACCENT)
    draw.text((W - 32, 28), f"UID {uid}", font=f_small, fill=GRAY, anchor="ra")
    if nickname:
        draw.text((32, 58), nickname, font=f_med, fill=WHITE)
    draw.line([(32, 82), (W - 32, 82)], fill=(80, 80, 100), width=1)

    # ── 开拓力 ────────────────────────────────────────────────────────────────
    stamina     = notes.current_stamina
    max_stamina = notes.max_stamina
    recover_sec = notes.stamina_recover_time.total_seconds()

    draw.text((32, 96), "开拓力", font=f_small, fill=GRAY)
    draw.text((32, 118), str(stamina), font=f_big, fill=SR_ACCENT)
    draw.text((32 + f_big.getlength(str(stamina)) + 4, 130), f"/ {max_stamina}",
              font=f_med, fill=GRAY)

    time_str = _fmt_time(int(recover_sec))
    draw.text((W - 32, 128), time_str, font=f_small, fill=GRAY, anchor="ra")

    draw_progress_bar(
        img, 32, 166, W - 64, 12,
        progress=stamina / max_stamina if max_stamina > 0 else 0,
        bg_color=(50, 50, 70),
        fill_color=SR_PURPLE,
        full_color=(231, 76, 60),
    )

    # 备用开拓力
    reserve = notes.current_reserve_stamina
    if reserve > 0:
        reserve_full = notes.is_reserve_stamina_full
        reserve_color = (231, 76, 60) if reserve_full else GRAY
        draw.text((32, 186), f"备用开拓力：{reserve}", font=f_small, fill=reserve_color)

    # ── 数据格 ─────────────────────────────────────────────────────────────────
    y_grid = 218
    grid_items = [
        ("每日实训", f"{notes.current_train_score}/{notes.max_train_score}"),
        ("模拟宇宙", f"{notes.current_rogue_score}/{notes.max_rogue_score}"),
    ]
    if notes.rogue_tourn_weekly_unlocked:
        grid_items.append((
            "差分积分",
            f"{notes.rogue_tourn_weekly_cur}/{notes.rogue_tourn_weekly_max}",
        ))

    cell_w = (W - 64) // max(len(grid_items), 1)
    for i, (label, value) in enumerate(grid_items):
        cx = 32 + i * cell_w + cell_w // 2
        draw_rounded_rect(draw, (32 + i * cell_w, y_grid,
                                 32 + (i + 1) * cell_w - 8, y_grid + 60),
                          radius=8, fill=(40, 40, 60))
        draw.text((cx, y_grid + 12), label, font=f_small, fill=GRAY, anchor="mt")
        draw.text((cx, y_grid + 34), value, font=f_med, fill=WHITE, anchor="mt")

    # ── 派遣 ──────────────────────────────────────────────────────────────────
    y_exp = y_grid + 76
    draw.text((32, y_exp), "委托派遣", font=f_small, fill=GRAY)
    draw.text((W - 32, y_exp), f"{notes.accepted_expedition_num}/{notes.total_expedition_num}",
              font=f_small, fill=WHITE, anchor="ra")
    y_exp += 22

    exps = notes.expeditions or []
    for exp in exps[:4]:
        finished   = getattr(exp, "finished", False)
        remaining  = getattr(exp, "remaining_time", None)
        rem_sec    = int(remaining.total_seconds()) if remaining else 0
        name       = getattr(exp, "name", "派遣角色")
        status_str = "已完成" if (finished or rem_sec <= 0) else _fmt_time(rem_sec)
        status_col = (46, 204, 113) if (finished or rem_sec <= 0) else GRAY

        draw.text((40, y_exp), f"• {name}", font=f_small, fill=WHITE)
        draw.text((W - 40, y_exp), status_str, font=f_small, fill=status_col, anchor="ra")
        y_exp += 22

    if not exps:
        draw.text((40, y_exp), "暂无派遣", font=f_small, fill=GRAY)

    return convert_img(img)


# ── 原神便笺卡片 ───────────────────────────────────────────────────────────────

async def render_genshin_notes(
    notes,
    uid: str,
    nickname: str = "",
) -> bytes:
    """原神便笺 → PNG bytes。"""
    W, H = 560, 460
    img = create_gradient_bg(W, H, GS_BG_TOP, GS_BG_BOT)

    # 半透明卡片层
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    draw_rounded_rect(ov_draw, (16, 16, W - 16, H - 16), radius=16,
                      fill=(20, 20, 35, 200))
    img = img.convert("RGBA")
    img.paste(overlay, (0, 0), overlay)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    f_big   = get_font(38)
    f_med   = get_font(22)
    f_small = get_font(18)
    f_title = get_font(28)

    # ── 标题栏 ────────────────────────────────────────────────────────────────
    draw.text((32, 28), "原神", font=f_title, fill=GS_GOLD)
    draw.text((W - 32, 28), f"UID {uid}", font=f_small, fill=GRAY, anchor="ra")
    if nickname:
        draw.text((32, 58), nickname, font=f_med, fill=WHITE)
    draw.line([(32, 82), (W - 32, 82)], fill=(80, 80, 60), width=1)

    # ── 树脂 ──────────────────────────────────────────────────────────────────
    resin     = notes.current_resin
    max_resin = notes.max_resin
    recover_s = int(notes.remaining_resin_recovery_time.total_seconds())

    draw.text((32, 96), "原粹树脂", font=f_small, fill=GRAY)
    draw.text((32, 118), str(resin), font=f_big, fill=GS_GOLD)
    draw.text((32 + f_big.getlength(str(resin)) + 4, 130),
              f"/ {max_resin}", font=f_med, fill=GRAY)
    draw.text((W - 32, 128), _fmt_time(recover_s), font=f_small, fill=GRAY, anchor="ra")

    draw_progress_bar(
        img, 32, 166, W - 64, 12,
        progress=resin / max_resin if max_resin > 0 else 0,
        bg_color=(50, 50, 40),
        fill_color=(200, 160, 60),
        full_color=(231, 76, 60),
    )

    # ── 数据格 ─────────────────────────────────────────────────────────────────
    y_grid = 196
    cell_w = (W - 64) // 2

    # 每日委托
    draw_rounded_rect(draw, (32, y_grid, 32 + cell_w - 8, y_grid + 60),
                      radius=8, fill=(40, 40, 30))
    draw.text((32 + (cell_w - 8) // 2, y_grid + 12), "每日委托",
              font=f_small, fill=GRAY, anchor="mt")
    draw.text((32 + (cell_w - 8) // 2, y_grid + 34),
              f"{notes.completed_commissions}/{notes.max_commissions}",
              font=f_med, fill=WHITE, anchor="mt")

    # 洞天宝钱
    draw_rounded_rect(draw, (32 + cell_w, y_grid, 32 + 2 * cell_w - 8, y_grid + 60),
                      radius=8, fill=(40, 40, 30))
    draw.text((32 + cell_w + (cell_w - 8) // 2, y_grid + 12), "洞天宝钱",
              font=f_small, fill=GRAY, anchor="mt")
    draw.text((32 + cell_w + (cell_w - 8) // 2, y_grid + 34),
              f"{notes.current_realm_currency}/{notes.max_realm_currency}",
              font=f_med, fill=WHITE, anchor="mt")

    # ── 质变仪 + 周本 ─────────────────────────────────────────────────────────
    y2 = y_grid + 68
    draw_rounded_rect(draw, (32, y2, 32 + cell_w - 8, y2 + 60),
                      radius=8, fill=(40, 40, 30))
    draw.text((32 + (cell_w - 8) // 2, y2 + 12), "质变仪",
              font=f_small, fill=GRAY, anchor="mt")
    if notes.transformer:
        trans_s = int(notes.transformer.recovery_time.total_seconds())
        trans_str = "可使用" if trans_s <= 0 else _fmt_time(trans_s)
    else:
        trans_str = "—"
    draw.text((32 + (cell_w - 8) // 2, y2 + 34), trans_str,
              font=f_med, fill=WHITE, anchor="mt")

    draw_rounded_rect(draw, (32 + cell_w, y2, 32 + 2 * cell_w - 8, y2 + 60),
                      radius=8, fill=(40, 40, 30))
    draw.text((32 + cell_w + (cell_w - 8) // 2, y2 + 12), "周本折扣",
              font=f_small, fill=GRAY, anchor="mt")
    draw.text((32 + cell_w + (cell_w - 8) // 2, y2 + 34),
              f"{notes.remaining_resin_discounts}/3",
              font=f_med, fill=WHITE, anchor="mt")

    # ── 派遣 ──────────────────────────────────────────────────────────────────
    y_exp = y2 + 76
    draw.text((32, y_exp), "探索派遣", font=f_small, fill=GRAY)
    draw.text((W - 32, y_exp), f"{len(notes.expeditions)} 人",
              font=f_small, fill=WHITE, anchor="ra")
    y_exp += 22

    for exp in notes.expeditions:
        finished = getattr(exp, "finished", False)
        remaining = getattr(exp, "remaining_time", None)
        rem_sec = int(remaining.total_seconds()) if remaining else 0
        char = getattr(exp, "character", None)
        name = char.name if char else getattr(exp, "name", "探索角色")
        status_str = "已完成" if (finished or rem_sec <= 0) else _fmt_time(rem_sec)
        status_col = (46, 204, 113) if (finished or rem_sec <= 0) else GRAY

        draw.text((40, y_exp), f"• {name}", font=f_small, fill=WHITE)
        draw.text((W - 40, y_exp), status_str, font=f_small, fill=status_col, anchor="ra")
        y_exp += 22

    if not notes.expeditions:
        draw.text((40, y_exp), "暂无派遣", font=f_small, fill=GRAY)

    return convert_img(img)
