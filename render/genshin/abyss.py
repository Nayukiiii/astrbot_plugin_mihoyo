from PIL import Image, ImageDraw

from ..base_card import GRAY, WHITE, GS_BG_BOT, GS_BG_TOP, GS_GOLD, convert_img, create_gradient_bg
from ..fonts.starrail_fonts import get_font


async def render_spiral_abyss(data, uid: str, previous: bool = False) -> bytes:
    period = "上期" if previous else "本期"
    floors = [f for f in getattr(data, "floors", []) if getattr(f, "floor", 0) >= 9]
    W, H_BASE = 900, 300
    H = H_BASE + 160 * len(floors) + 40
    img = create_gradient_bg(W, H, GS_BG_TOP, GS_BG_BOT)
    draw = ImageDraw.Draw(img)

    f_big = get_font(42)
    f_med = get_font(28)
    f_small = get_font(22)

    draw.text((W // 2, 50), f"深境螺旋  {period}", font=f_big, fill=GS_GOLD, anchor="mm")
    draw.text((W // 2, 100), f"UID {uid}", font=f_small, fill=GRAY, anchor="mm")
    draw.text((180, 160), f"最深：{getattr(data, 'max_floor', '--')}", font=f_med, fill=WHITE)
    draw.text((W - 180, 160), f"★ {getattr(data, 'total_stars', 0)}/36", font=f_big, fill=(244, 208, 63), anchor="ra")
    draw.line([(40, 220), (W - 40, 220)], fill=(80, 80, 60), width=1)

    y = H_BASE
    for floor in reversed(floors):
        for chamber in reversed(getattr(floor, "chambers", [])):
            draw.text((60, y + 10), f"第 {floor.floor}-{chamber.chamber} 间", font=f_med, fill=WHITE)
            stars = getattr(chamber, "stars", 0)
            draw.text((W - 60, y + 10), "★" * stars + "☆" * (3 - stars), font=f_med, fill=(244, 208, 63), anchor="ra")
            for hi, half_attr in enumerate(("first_half", "second_half")):
                half = getattr(chamber, half_attr, None)
                if not half:
                    continue
                label = "上半" if hi == 0 else "下半"
                names = "、".join(c.name for c in getattr(half, "characters", [])) or "--"
                draw.text((60, y + 46 + hi * 26), f"{label}：{names}", font=f_small, fill=GRAY)
            y += 100

    return convert_img(img)
