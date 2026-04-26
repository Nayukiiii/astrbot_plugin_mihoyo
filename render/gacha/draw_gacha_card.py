"""
render/gacha/draw_gacha_card.py
抽卡统计卡片 PIL 渲染。
"""

from pathlib import Path
from PIL import Image, ImageDraw

from ..base_card import (
    WHITE, GRAY, convert_img,
    SR_ACCENT, SR_BG_TOP, SR_BG_BOT,
    GS_GOLD, GS_BG_TOP, GS_BG_BOT,
    create_gradient_bg, draw_rounded_rect,
)
from ..fonts.starrail_fonts import get_font

_TEXTURE_DIR = Path(__file__).parent / "texture2D"
_TEXTURE_DIR.mkdir(exist_ok=True)

POOL_DISPLAY = {
    "genshin":  {
        "character": "角色活动祈愿", "weapon": "武器活动祈愿",
        "standard": "常驻祈愿",     "beginner": "新手祈愿",
    },
    "starrail": {
        "character": "角色活动跃迁", "weapon": "光锥活动跃迁",
        "standard": "群星跃迁",     "beginner": "新手跃迁",
    },
}


async def render_gacha_card(
    stats: dict, game: str, pool_type: str, uid: str, nickname: str = "",
) -> bytes:
    is_sr     = game == "starrail"
    bg_top    = SR_BG_TOP if is_sr else GS_BG_TOP
    bg_bot    = SR_BG_BOT if is_sr else GS_BG_BOT
    accent    = SR_ACCENT if is_sr else GS_GOLD
    game_tag  = "崩坏：星穹铁道" if is_sr else "原神"
    pool_name = POOL_DISPLAY.get(game, {}).get(pool_type, pool_type)

    W, H = 600, 520
    img = create_gradient_bg(W, H, bg_top, bg_bot)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)
    draw_rounded_rect(ov, (16, 16, W - 16, H - 16), radius=16, fill=(20, 20, 35, 200))
    img = img.convert("RGBA")
    img.paste(overlay, (0, 0), overlay)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    f_big   = get_font(38)
    f_med   = get_font(24)
    f_small = get_font(20)
    f_title = get_font(28)

    draw.text((32, 28), game_tag, font=f_title, fill=accent)
    draw.text((W - 32, 28), f"UID {uid}", font=f_small, fill=GRAY, anchor="ra")
    draw.text((32, 60), pool_name, font=f_med, fill=WHITE)
    draw.line([(32, 96), (W - 32, 96)], fill=(80, 80, 100), width=1)

    total = stats.get("total", 0)
    s5    = stats.get("five_star", 0)
    s4    = stats.get("four_star", 0)
    pity  = stats.get("current_pity", 0)

    draw.text((32, 112), "总抽数", font=f_small, fill=GRAY)
    draw.text((32, 138), str(total), font=f_big, fill=accent)

    cell_w = (W - 64) // 3
    cells = [
        ("五星", str(s5), (244, 208, 63)),
        ("四星", str(s4), (167, 139, 250)),
        ("当前保底", str(pity), WHITE),
    ]
    y_g = 196
    for i, (label, val, col) in enumerate(cells):
        x0 = 32 + i * cell_w
        draw_rounded_rect(draw, (x0, y_g, x0 + cell_w - 8, y_g + 70),
                          radius=8, fill=(40, 40, 60))
        draw.text((x0 + (cell_w - 8) // 2, y_g + 12), label,
                  font=f_small, fill=GRAY, anchor="mt")
        draw.text((x0 + (cell_w - 8) // 2, y_g + 36), val,
                  font=f_med, fill=col, anchor="mt")

    y_list = y_g + 90
    draw.text((32, y_list), "五星记录", font=f_small, fill=GRAY)
    y_list += 26

    for rec in stats.get("five_star_list", [])[-8:]:
        name   = rec.get("name", "?")
        pity_c = rec.get("pity_count", 0)
        is_up  = rec.get("is_up")
        up_tag = " UP" if is_up == 1 else (" 歪" if is_up == 0 else "")
        col    = (244, 208, 63) if is_up != 0 else (255, 140, 0)
        draw.text((40, y_list), f"• {name}{up_tag}", font=f_small, fill=col)
        draw.text((W - 40, y_list), f"{pity_c} 抽", font=f_small, fill=GRAY, anchor="ra")
        y_list += 24

    if not stats.get("five_star_list"):
        draw.text((40, y_list), "暂无五星记录", font=f_small, fill=GRAY)

    return convert_img(img)
