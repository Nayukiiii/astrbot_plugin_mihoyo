from typing import Any

from PIL import Image, ImageDraw

from .common import (
    BLUE,
    FIRST,
    GOLD,
    GRAY,
    MUTED,
    PURPLE,
    RED,
    SECOND,
    WHITE,
    base_canvas,
    convert_img,
    get_font,
    getv,
    listv,
    load_rgba,
    paste_panel,
    small_progress,
    sr_texture,
    text_fit,
)


GRID_MODULE = "starrailuid_grid_fight"
WIDTH = 1200
MARGIN = 64
CARD_FILL = (255, 255, 255, 224)
DEEP_PANEL = (20, 18, 34, 190)


def _to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    try:
        return int(str(value).replace(",", "").strip())
    except Exception:
        return default


def _grid_canvas(height: int) -> Image.Image:
    bg = load_rgba(sr_texture(GRID_MODULE, "bg.jpg"))
    if not bg:
        return base_canvas(WIDTH, height).convert("RGB")
    if height <= bg.height:
        return bg.crop((0, 0, WIDTH, height)).convert("RGB")
    img = Image.new("RGB", (WIDTH, height), (64, 58, 143))
    y = 0
    while y < height:
        crop_h = min(bg.height, height - y)
        img.paste(bg.crop((0, 0, WIDTH, crop_h)).convert("RGB"), (0, y))
        y += crop_h
    return img


def _paste_asset(img: Image.Image, name: str, xy: tuple[int, int], size: tuple[int, int] | None = None) -> None:
    asset = load_rgba(sr_texture(GRID_MODULE, name), size)
    if asset:
        img.paste(asset, xy, asset)


def _division_name(division) -> str:
    return str(
        getv(
            division,
            "name_with_num",
            getv(division, "name", getv(division, "level", "--")),
        )
        or "--"
    )


def _draw_header(img: Image.Image, data, uid: str, nickname: str) -> int:
    brief = getv(data, "grid_fight_brief", None)
    division = getv(brief, "division", None)

    _paste_asset(img, "title_bg.png", (0, 0), (WIDTH, 800))

    draw = ImageDraw.Draw(img)
    draw.text((MARGIN, 74), "货币战争", font=get_font(56), fill=WHITE)
    draw.text((MARGIN + 2, 138), nickname or f"UID {uid}", font=get_font(28), fill=(222, 226, 255))
    draw.text((MARGIN + 2, 180), f"UID {uid}", font=get_font(22), fill=(168, 174, 218))

    division_text = _division_name(division)
    draw.text((WIDTH - MARGIN, 76), division_text, font=get_font(34), fill=GOLD, anchor="ra")
    if getv(division, "is_promotion", False):
        draw.text((WIDTH - MARGIN, 122), "晋级中", font=get_font(24), fill=(129, 232, 148), anchor="ra")

    season_level = str(getv(brief, "season_level", "--") or "--")
    weekly_cur = _to_int(getv(brief, "weekly_score_cur", 0))
    weekly_max = _to_int(getv(brief, "weekly_score_max", 0))
    quest_cur = _to_int(getv(brief, "quest_cur", 0))
    quest_max = _to_int(getv(brief, "quest_max", 0))
    handbook = str(getv(brief, "handbook_progress", "--") or "--")
    trait = str(getv(brief, "trait_progress", "--") or "--")

    y = 250
    paste_panel(img, (MARGIN, y, WIDTH - MARGIN, y + 250), radius=22, fill=DEEP_PANEL)
    draw = ImageDraw.Draw(img)
    summary = [
        ("赛季等级", season_level, PURPLE),
        ("本期积分", f"{weekly_cur}/{weekly_max}" if weekly_max else str(weekly_cur), GOLD),
        ("任务进度", f"{quest_cur}/{quest_max}" if quest_max else str(quest_cur), BLUE),
        ("图鉴进度", handbook, WHITE),
    ]
    cell_w = (WIDTH - MARGIN * 2 - 48) // 4
    for index, (label, value, color) in enumerate(summary):
        x0 = MARGIN + 24 + index * cell_w
        draw.text((x0, y + 32), label, font=get_font(22), fill=(190, 196, 226))
        text_fit(draw, (x0, y + 68), value, 34, color, cell_w - 22)
    small_progress(img, MARGIN + 28, y + 170, WIDTH - MARGIN * 2 - 56, weekly_cur, weekly_max, GOLD)
    draw.text((MARGIN + 28, y + 194), f"特性进度 {trait}", font=get_font(22), fill=(190, 196, 226))
    return y + 300


def _archive_height(archive) -> int:
    lineup = getv(archive, "lineup", None)
    front = len(listv(getv(lineup, "front_roles", [])))
    back = len(listv(getv(lineup, "back_roles", [])))
    rows = max(front, back, 1)
    return 260 + rows * 92


def _rarity_color(role) -> tuple[int, int, int]:
    rarity = _to_int(getv(role, "rarity", 0))
    if rarity >= 5:
        return (235, 176, 72)
    if rarity == 4:
        return (168, 117, 255)
    return (130, 153, 190)


def _role_title(role) -> str:
    name = str(getv(role, "name", "") or f"#{getv(role, 'avatar_id', '--')}")
    star = str(getv(role, "star", "") or "")
    trial = " 试用" if getv(role, "is_trial", False) else ""
    return f"{name}{f' {star}★' if star else ''}{trial}"


def _equip_text(role) -> str:
    equips = listv(getv(role, "equip_list", []))
    if not equips:
        return "未记录装备"
    names = []
    for equip in equips[:3]:
        name = str(getv(equip, "name", "") or getv(equip, "category", "装备"))
        names.append(name)
    suffix = " ..." if len(equips) > 3 else ""
    return " / ".join(names) + suffix


def _draw_role_row(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    role,
    side_color: tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle((x0, y0, x1, y1), radius=14, fill=(246, 245, 252), outline=(222, 221, 235), width=1)
    draw.rounded_rectangle((x0, y0, x0 + 8, y1), radius=4, fill=side_color)
    draw.ellipse((x0 + 18, y0 + 18, x0 + 66, y0 + 66), fill=_rarity_color(role))
    role_type = str(getv(role, "role_type", "") or getv(role, "pos", "") or "?")
    draw.text((x0 + 42, y0 + 31), role_type[:2], font=get_font(18), fill=WHITE, anchor="mm")
    text_fit(draw, (x0 + 80, y0 + 16), _role_title(role), 22, FIRST, x1 - x0 - 104)
    text_fit(draw, (x0 + 80, y0 + 48), _equip_text(role), 18, MUTED, x1 - x0 - 104)


def _draw_archive(img: Image.Image, archive, index: int, y: int) -> int:
    height = _archive_height(archive)
    paste_panel(img, (MARGIN, y, WIDTH - MARGIN, y + height), radius=24, fill=CARD_FILL)
    draw = ImageDraw.Draw(img)

    brief = getv(archive, "brief", None)
    archive_type = str(getv(archive, "archive_type", f"存档 {index + 1}") or f"存档 {index + 1}")
    division = getv(brief, "division", None)
    division_text = _division_name(division)
    archive_rank = str(getv(brief, "archive_rank", "--") or "--")
    total_coin = str(getv(brief, "total_coin", "--") or "--")
    remain_hp = str(getv(brief, "remain_hp", "--") or "--")
    lineup_coin = str(getv(brief, "lineup_coin", "--") or "--")
    archive_time = str(getv(brief, "archive_time", "") or "")

    draw.text((MARGIN + 32, y + 28), archive_type, font=get_font(32), fill=FIRST)
    draw.text((WIDTH - MARGIN - 32, y + 32), archive_time, font=get_font(18), fill=MUTED, anchor="ra")
    draw.text((MARGIN + 34, y + 78), division_text, font=get_font(22), fill=SECOND)
    draw.text((WIDTH - MARGIN - 32, y + 76), f"评级 {archive_rank}", font=get_font(24), fill=GOLD, anchor="ra")

    stats = [
        ("总硬币", total_coin, GOLD),
        ("剩余 HP", remain_hp, RED),
        ("阵容价值", lineup_coin, BLUE),
    ]
    stat_w = (WIDTH - MARGIN * 2 - 96) // 3
    stat_y = y + 122
    for i, (label, value, color) in enumerate(stats):
        sx = MARGIN + 32 + i * (stat_w + 16)
        draw.rounded_rectangle((sx, stat_y, sx + stat_w, stat_y + 76), radius=14, fill=(239, 238, 247))
        draw.text((sx + 18, stat_y + 12), label, font=get_font(18), fill=MUTED)
        text_fit(draw, (sx + 18, stat_y + 38), value, 26, color, stat_w - 36)

    lineup = getv(archive, "lineup", None)
    front = listv(getv(lineup, "front_roles", []))
    back = listv(getv(lineup, "back_roles", []))

    left_x = MARGIN + 32
    right_x = WIDTH // 2 + 12
    list_y = y + 232
    col_w = WIDTH // 2 - MARGIN - 48
    draw.text((left_x, y + 210), "前排", font=get_font(22), fill=FIRST)
    draw.text((right_x, y + 210), "后排", font=get_font(22), fill=FIRST)

    rows = max(len(front), len(back), 1)
    for row in range(rows):
        row_y = list_y + row * 92
        if row < len(front):
            _draw_role_row(draw, (left_x, row_y, left_x + col_w, row_y + 74), front[row], PURPLE)
        else:
            draw.rounded_rectangle((left_x, row_y, left_x + col_w, row_y + 74), radius=14, fill=(240, 240, 246))
            draw.text((left_x + col_w // 2, row_y + 37), "空位", font=get_font(20), fill=MUTED, anchor="mm")
        if row < len(back):
            _draw_role_row(draw, (right_x, row_y, right_x + col_w, row_y + 74), back[row], BLUE)
        else:
            draw.rounded_rectangle((right_x, row_y, right_x + col_w, row_y + 74), radius=14, fill=(240, 240, 246))
            draw.text((right_x + col_w // 2, row_y + 37), "空位", font=get_font(20), fill=MUTED, anchor="mm")

    return y + height + 34


async def render_grid_fight_card(data, uid: str, nickname: str = "") -> bytes:
    """Render Currency Wars data from GridFightCurrency."""
    archives = listv(getv(data, "grid_fight_archive_list", []))
    total_height = 620 + sum(_archive_height(item) + 34 for item in archives[:6])
    total_height = max(total_height, 920)
    img = _grid_canvas(total_height)

    y = _draw_header(img, data, uid, nickname)
    brief = getv(data, "grid_fight_brief", None)
    has_played = bool(getv(brief, "has_played", bool(archives)))
    draw = ImageDraw.Draw(img)

    if not has_played:
        paste_panel(img, (MARGIN, y + 30, WIDTH - MARGIN, y + 250), radius=24, fill=CARD_FILL)
        draw = ImageDraw.Draw(img)
        draw.text((WIDTH // 2, y + 110), "暂无货币战争数据", font=get_font(34), fill=FIRST, anchor="mm")
        draw.text((WIDTH // 2, y + 160), "完成一次挑战后即可生成战绩卡", font=get_font(24), fill=MUTED, anchor="mm")
        return convert_img(img)

    if not archives:
        paste_panel(img, (MARGIN, y + 30, WIDTH - MARGIN, y + 250), radius=24, fill=CARD_FILL)
        draw = ImageDraw.Draw(img)
        draw.text((WIDTH // 2, y + 110), "暂无存档记录", font=get_font(34), fill=FIRST, anchor="mm")
        draw.text((WIDTH // 2, y + 160), "接口未返回 grid_fight_archive_list", font=get_font(22), fill=MUTED, anchor="mm")
        return convert_img(img)

    draw.text((MARGIN, y + 14), "存档记录", font=get_font(34), fill=WHITE)
    y += 72
    for index, archive in enumerate(archives[:6]):
        y = _draw_archive(img, archive, index, y)

    if len(archives) > 6:
        draw = ImageDraw.Draw(img)
        draw.text((WIDTH // 2, y), f"还有 {len(archives) - 6} 条存档未展示", font=get_font(22), fill=GRAY, anchor="mm")

    return convert_img(img)
