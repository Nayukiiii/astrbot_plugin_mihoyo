"""
render/fonts/starrail_fonts.py
字体加载工具。

字体文件放在 render/fonts/assets/ 目录下。
首次使用时如未找到字体，自动尝试系统字体；
如需高质量渲染，请手动下载字体文件到 assets/ 目录。

推荐字体：
  - HYWenHei-85W.ttf（汉仪文黑）
  - 或任意支持中文的 TTF 字体
"""

from pathlib import Path
from functools import lru_cache

from PIL import ImageFont
from astrbot.api import logger

_FONTS_DIR = Path(__file__).parent / "assets"
_FONTS_DIR.mkdir(exist_ok=True)

# 系统字体备用路径
_SYSTEM_FONTS = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",      # Linux WQY
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Noto CJK
    "/System/Library/Fonts/PingFang.ttc",                   # macOS
    "C:/Windows/Fonts/msyh.ttc",                            # Windows 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",                          # Windows 黑体
]

# 本地字体文件名（按优先级）
_LOCAL_FONTS = [
    "HYWenHei-85W.ttf",
    "HYWenHei-55W.ttf",
    "NotoSansSC-Regular.ttf",
    "SourceHanSans-Regular.ttc",
]


def _find_font_path() -> Path | None:
    """查找可用字体文件路径。"""
    # 优先本地 assets/
    for name in _LOCAL_FONTS:
        p = _FONTS_DIR / name
        if p.exists():
            return p
    # 降级到系统字体
    for p in _SYSTEM_FONTS:
        if Path(p).exists():
            return Path(p)
    return None


@lru_cache(maxsize=32)
def get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """获取指定大小的字体（缓存）。"""
    font_path = _find_font_path()
    if font_path:
        try:
            return ImageFont.truetype(str(font_path), size)
        except Exception as e:
            logger.warning(f"[render] 加载字体失败 {font_path}: {e}")
    logger.warning(f"[render] 未找到字体文件，使用 PIL 默认字体（中文可能显示为框）")
    return ImageFont.load_default()


# 预定义常用字号（对应 StarRailUID 的 sr_font_XX）
def sr_font_18() -> ImageFont.FreeTypeFont: return get_font(18)
def sr_font_22() -> ImageFont.FreeTypeFont: return get_font(22)
def sr_font_26() -> ImageFont.FreeTypeFont: return get_font(26)
def sr_font_28() -> ImageFont.FreeTypeFont: return get_font(28)
def sr_font_30() -> ImageFont.FreeTypeFont: return get_font(30)
def sr_font_34() -> ImageFont.FreeTypeFont: return get_font(34)
def sr_font_38() -> ImageFont.FreeTypeFont: return get_font(38)
def sr_font_42() -> ImageFont.FreeTypeFont: return get_font(42)
