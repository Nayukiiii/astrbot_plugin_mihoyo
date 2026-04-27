from PIL import Image, ImageDraw

from ..base_card import (
    GRAY,
    WHITE,
    GS_BG_BOT,
    GS_BG_TOP,
    GS_GOLD,
    convert_img,
    create_gradient_bg,
    draw_progress_bar,
    draw_rounded_rect,
)
from ..fonts.starrail_fonts import get_font


def _seconds(value) -> int:
    if value is None:
        return 0
    if hasattr(value, "total_seconds"):
        return int(value.total_seconds())
    return int(value)


def _fmt_time(seconds: int) -> str:
    if seconds <= 0:
        return "已满"
    hour, minute = divmod(seconds // 60, 60)
    return f"{hour}小时{minute}分钟" if hour else f"{minute}分钟"


async def render_genshin_notes(notes, uid: str, nickname: str = "") -> bytes:
    W, H = 560, 460
    img = create_gradient_bg(W, H, GS_BG_TOP, GS_BG_BOT)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)
    draw_rounded_rect(ov, (16, 16, W - 16, H - 16), radius=16, fill=(20, 20, 35, 200))
    img = img.convert("RGBA")
    img.paste(overlay, (0, 0), overlay)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    f_big = get_font(38)
    f_med = get_font(22)
    f_small = get_font(18)
    f_title = get_font(28)

    draw.text((32, 28), "原神", font=f_title, fill=GS_GOLD)
    draw.text((W - 32, 28), f"UID {uid}", font=f_small, fill=GRAY, anchor="ra")
    if nickname:
        draw.text((32, 58), nickname, font=f_med, fill=WHITE)
    draw.line([(32, 82), (W - 32, 82)], fill=(80, 80, 60), width=1)

    resin = int(getattr(notes, "current_resin", 0) or 0)
    max_resin = int(getattr(notes, "max_resin", 160) or 160)
    recover_s = _seconds(getattr(notes, "remaining_resin_recovery_time", 0))

    draw.text((32, 96), "原粹树脂", font=f_small, fill=GRAY)
    draw.text((32, 118), str(resin), font=f_big, fill=GS_GOLD)
    draw.text((32 + f_big.getlength(str(resin)) + 4, 130), f"/ {max_resin}", font=f_med, fill=GRAY)
    draw.text((W - 32, 128), _fmt_time(recover_s), font=f_small, fill=GRAY, anchor="ra")
    draw_progress_bar(
        img,
        32,
        166,
        W - 64,
        12,
        progress=resin / max_resin if max_resin else 0,
        bg_color=(50, 50, 40),
        fill_color=(200, 160, 60),
        full_color=(231, 76, 60),
    )

    y_grid = 196
    cell_w = (W - 64) // 2
    cells = [
        ("每日委托", f"{getattr(notes, 'completed_commissions', 0)}/{getattr(notes, 'max_commissions', 4)}"),
        ("洞天宝钱", f"{getattr(notes, 'current_realm_currency', 0)}/{getattr(notes, 'max_realm_currency', 2400)}"),
    ]
    for i, (label, value) in enumerate(cells):
        x = 32 + i * cell_w
        draw_rounded_rect(draw, (x, y_grid, x + cell_w - 8, y_grid + 60), radius=8, fill=(40, 40, 30))
        draw.text((x + (cell_w - 8) // 2, y_grid + 12), label, font=f_small, fill=GRAY, anchor="mt")
        draw.text((x + (cell_w - 8) // 2, y_grid + 34), value, font=f_med, fill=WHITE, anchor="mt")

    y2 = y_grid + 68
    transformer = getattr(notes, "transformer", None)
    if transformer:
        trans_s = _seconds(getattr(transformer, "recovery_time", 0))
        trans_str = "可使用" if trans_s <= 0 else _fmt_time(trans_s)
    else:
        trans_str = "--"
    cells = [
        ("质变仪", trans_str),
        ("周本折扣", f"{getattr(notes, 'remaining_resin_discounts', 0)}/3"),
    ]
    for i, (label, value) in enumerate(cells):
        x = 32 + i * cell_w
        draw_rounded_rect(draw, (x, y2, x + cell_w - 8, y2 + 60), radius=8, fill=(40, 40, 30))
        draw.text((x + (cell_w - 8) // 2, y2 + 12), label, font=f_small, fill=GRAY, anchor="mt")
        draw.text((x + (cell_w - 8) // 2, y2 + 34), value, font=f_med, fill=WHITE, anchor="mt")

    expeditions = list(getattr(notes, "expeditions", []) or [])
    y_exp = y2 + 76
    draw.text((32, y_exp), "探索派遣", font=f_small, fill=GRAY)
    draw.text((W - 32, y_exp), f"{len(expeditions)} 人", font=f_small, fill=WHITE, anchor="ra")
    y_exp += 22
    for exp in expeditions[:4]:
        finished = bool(getattr(exp, "finished", False))
        rem_sec = _seconds(getattr(exp, "remaining_time", 0))
        char = getattr(exp, "character", None)
        name = getattr(char, "name", "") if char else getattr(exp, "name", "探索角色")
        status = "已完成" if finished or rem_sec <= 0 else _fmt_time(rem_sec)
        draw.text((40, y_exp), f"• {name}", font=f_small, fill=WHITE)
        draw.text((W - 40, y_exp), status, font=f_small, fill=GRAY, anchor="ra")
        y_exp += 22
    if not expeditions:
        draw.text((40, y_exp), "暂无派遣", font=f_small, fill=GRAY)

    return convert_img(img)
