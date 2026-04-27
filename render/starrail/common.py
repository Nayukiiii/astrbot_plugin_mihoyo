from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw

from ..base_card import (
    GRAY,
    WHITE,
    convert_img,
    create_gradient_bg,
    draw_progress_bar,
    draw_rounded_rect,
)
from ..fonts.starrail_fonts import get_font
from ..starrailuid_assets import first_existing, vendor_texture


FIRST = (29, 29, 29)
SECOND = (98, 98, 98)
MUTED = (132, 132, 132)
RED = (235, 61, 75)
GOLD = (242, 196, 99)
BLUE = (80, 148, 255)
PURPLE = (126, 106, 210)
PANEL = (255, 251, 242, 225)
CARD = (255, 255, 255, 225)
CARD_LINE = (230, 218, 197, 255)
STAR_TOP = (18, 24, 45)
STAR_BOT = (42, 36, 80)


def getv(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def listv(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return list(value) if isinstance(value, Iterable) and not isinstance(value, (str, bytes)) else []


def seconds(value: Any) -> int:
    if value is None:
        return 0
    if hasattr(value, "total_seconds"):
        return int(value.total_seconds())
    try:
        return int(value)
    except Exception:
        return 0


def hhmm_cn(value: Any) -> str:
    total = max(0, seconds(value))
    minute, _ = divmod(total, 60)
    hour, minute = divmod(minute, 60)
    return f"{hour:02d}小时{minute:02d}分"


def date_text(value: Any) -> str:
    if not value:
        return "--"
    year = getv(value, "year", 0)
    month = getv(value, "month", 0)
    day = getv(value, "day", 0)
    hour = getv(value, "hour", 0)
    minute = getv(value, "minute", 0)
    if year and month and day:
        return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"
    return str(value)


def sr_texture(module: str, name: str, dirname: str = "texture2D") -> Path | None:
    path = vendor_texture(module, dirname) / name
    return path if path.exists() else None


def load_rgba(path: Path | None, size: tuple[int, int] | None = None) -> Image.Image | None:
    if not path or not path.exists():
        return None
    try:
        img = Image.open(path).convert("RGBA")
        return img.resize(size, Image.Resampling.LANCZOS) if size else img
    except Exception:
        return None


def base_canvas(width: int, height: int, bg_path: Path | None = None) -> Image.Image:
    if bg_path and bg_path.exists():
        try:
            return Image.open(bg_path).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        except Exception:
            pass
    return create_gradient_bg(width, height, STAR_TOP, STAR_BOT)


def paste_panel(img: Image.Image, xy: tuple[int, int, int, int], radius: int = 18, fill: tuple = CARD) -> None:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw_rounded_rect(draw, xy, radius=radius, fill=fill, outline=CARD_LINE, width=1)
    img.paste(overlay, (0, 0), overlay)


def text_fit(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font_size: int, fill: tuple, max_width: int, anchor: str = "la") -> None:
    text = str(text)
    font = get_font(font_size)
    while font_size > 12 and draw.textlength(text, font=font) > max_width:
        font_size -= 1
        font = get_font(font_size)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def stat_cell(
    img: Image.Image,
    xy: tuple[int, int, int, int],
    label: str,
    value: str,
    accent: tuple = FIRST,
    sub: str = "",
) -> None:
    paste_panel(img, xy, radius=14, fill=(255, 255, 255, 214))
    draw = ImageDraw.Draw(img)
    x0, y0, x1, _ = xy
    draw.text((x0 + 18, y0 + 14), label, font=get_font(20), fill=SECOND)
    text_fit(draw, (x0 + 18, y0 + 44), value, 30, accent, x1 - x0 - 36)
    if sub:
        text_fit(draw, (x1 - 18, y0 + 20), sub, 18, MUTED, x1 - x0 - 36, anchor="ra")


def small_progress(
    img: Image.Image,
    x: int,
    y: int,
    width: int,
    current: int,
    total: int,
    fill: tuple = PURPLE,
) -> None:
    draw_progress_bar(
        img,
        x,
        y,
        width,
        12,
        progress=current / total if total else 0,
        bg_color=(220, 214, 204),
        fill_color=fill,
        full_color=RED,
        radius=6,
    )


__all__ = [
    "BLUE",
    "FIRST",
    "GOLD",
    "GRAY",
    "MUTED",
    "PURPLE",
    "RED",
    "SECOND",
    "WHITE",
    "base_canvas",
    "convert_img",
    "date_text",
    "first_existing",
    "get_font",
    "getv",
    "hhmm_cn",
    "listv",
    "load_rgba",
    "paste_panel",
    "seconds",
    "small_progress",
    "sr_texture",
    "stat_cell",
    "text_fit",
]
