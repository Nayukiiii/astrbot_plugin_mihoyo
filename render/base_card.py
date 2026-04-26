"""
render/base_card.py
PIL/Pillow 绘图基础工具。

替代 gsuid_core 中的：
  - convert_img(img) -> bytes
  - draw_pic_with_ring(img, size) -> Image
  - 渐变背景、圆角矩形等通用绘图工具
"""

import io
import math
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter

# 颜色常量
WHITE  = (255, 255, 255)
GRAY   = (175, 175, 175)
DARK   = (30, 30, 40)
BLACK  = (0, 0, 0, 255)

# 崩铁主题色
SR_PURPLE  = (124, 111, 205)
SR_ACCENT  = (167, 139, 250)
SR_BG_TOP  = (13, 27, 42)
SR_BG_MID  = (27, 40, 56)
SR_BG_BOT  = (45, 27, 105)

# 原神主题色
GS_GOLD    = (232, 176, 75)
GS_BG_TOP  = (26, 26, 46)
GS_BG_MID  = (22, 33, 62)
GS_BG_BOT  = (15, 52, 96)


def convert_img(img: Image.Image) -> bytes:
    """PIL Image → PNG bytes（替代 gsuid_core convert_img）。"""
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def draw_pic_with_ring(
    img: Image.Image,
    size: int,
    ring_color: Optional[Tuple] = None,
    draw_ring: bool = True,
) -> Image.Image:
    """
    将图片裁剪为圆形，可选加圆环边框（替代 gsuid_core draw_pic_with_ring）。
    """
    img = img.resize((size, size), Image.LANCZOS).convert("RGBA")

    # 创建圆形 mask
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)

    # 应用 mask
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask=mask)

    if draw_ring:
        ring_col = ring_color or (255, 255, 255, 180)
        ring_draw = ImageDraw.Draw(result)
        lw = max(2, size // 60)
        ring_draw.ellipse((lw // 2, lw // 2, size - lw // 2, size - lw // 2),
                          outline=ring_col, width=lw)

    return result


def create_gradient_bg(
    width: int,
    height: int,
    color_top: Tuple,
    color_bot: Tuple,
) -> Image.Image:
    """创建垂直渐变背景。"""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / height
        r = int(color_top[0] + (color_bot[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bot[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bot[2] - color_top[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return img


def draw_rounded_rect(
    draw: ImageDraw.Draw,
    xy: Tuple,
    radius: int,
    fill: Optional[Tuple] = None,
    outline: Optional[Tuple] = None,
    width: int = 1,
):
    """绘制圆角矩形。"""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=fill,
                            outline=outline, width=width)


def draw_progress_bar(
    img: Image.Image,
    x: int, y: int,
    width: int, height: int,
    progress: float,
    bg_color: Tuple = (60, 60, 80),
    fill_color: Tuple = (124, 111, 205),
    full_color: Optional[Tuple] = None,
    radius: int = 4,
):
    """绘制进度条。progress 为 0.0-1.0。"""
    draw = ImageDraw.Draw(img)
    # 背景
    draw_rounded_rect(draw, (x, y, x + width, y + height), radius, fill=bg_color)
    # 填充
    fill_w = max(radius * 2, int(width * min(1.0, progress)))
    color = (full_color or (231, 76, 60)) if progress >= 1.0 else fill_color
    draw_rounded_rect(draw, (x, y, x + fill_w, y + height), radius, fill=color)


def paste_with_alpha(base: Image.Image, overlay: Image.Image, pos: Tuple):
    """带 alpha 通道的粘贴。"""
    if overlay.mode != "RGBA":
        overlay = overlay.convert("RGBA")
    base.paste(overlay, pos, mask=overlay)


def draw_text_shadow(
    draw: ImageDraw.Draw,
    xy: Tuple,
    text: str,
    font,
    fill: Tuple = WHITE,
    shadow_color: Tuple = (0, 0, 0, 120),
    shadow_offset: Tuple = (1, 1),
    anchor: str = "la",
):
    """带阴影的文字（增加可读性）。"""
    sx, sy = xy[0] + shadow_offset[0], xy[1] + shadow_offset[1]
    draw.text((sx, sy), text, font=font, fill=shadow_color, anchor=anchor)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)
