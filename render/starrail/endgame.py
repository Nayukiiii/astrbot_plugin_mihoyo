from PIL import Image, ImageDraw

from .common import (
    BLUE,
    FIRST,
    GOLD,
    GRAY,
    MUTED,
    PURPLE,
    RED,
    WHITE,
    base_canvas,
    convert_img,
    date_text,
    get_font,
    getv,
    listv,
    load_rgba,
    paste_panel,
    sr_texture,
    text_fit,
)


def _stars_for_floor(floor) -> int:
    return int(getv(floor, "stars", getv(floor, "star_num", 0)) or 0)


def _floor_list(data) -> list:
    floors = listv(getv(data, "floors", None))
    if floors:
        return floors
    return listv(getv(data, "all_floor_detail", None))


def _node_chars(node) -> list:
    chars = listv(getv(node, "characters", None))
    if chars:
        return chars
    return listv(getv(node, "avatars", None))


def _char_name(char) -> str:
    name = getv(char, "name", "")
    if name:
        return str(name)
    cid = getv(char, "id", "")
    level = getv(char, "level", "")
    return f"#{cid} Lv.{level}" if cid else "角色"


def _summary(data) -> tuple[int, str, int, bool]:
    stars = int(getv(data, "total_stars", getv(data, "star_num", 0)) or 0)
    max_floor = str(getv(data, "max_floor", "--") or "--")
    battle_num = int(getv(data, "battle_num", 0) or 0)
    has_data = bool(getv(data, "has_data", True))
    return stars, max_floor, battle_num, has_data


async def render_endgame(
    data,
    uid: str,
    title: str,
    previous: bool = False,
    module: str = "starrailuid_abyss",
    accent: tuple = PURPLE,
    max_stars: int = 12,
) -> bytes:
    period = "上期" if previous else "本期"
    floors = _floor_list(data)
    stars, max_floor, battle_num, has_data = _summary(data)
    width = 900
    head_h = 300
    floor_h = 210
    height = max(660, head_h + max(1, len(floors)) * floor_h + 40)

    img = base_canvas(width, height, sr_texture(module, "bg.jpg"))
    draw = ImageDraw.Draw(img)
    paste_panel(img, (34, 34, width - 34, 260), radius=20, fill=(22, 22, 34, 190))
    draw = ImageDraw.Draw(img)
    draw.text((64, 62), f"{title} · {period}", font=get_font(42), fill=accent)
    draw.text((64, 118), f"UID {uid}", font=get_font(22), fill=GRAY)
    draw.text((64, 168), f"最深 {max_floor}", font=get_font(28), fill=WHITE)
    draw.text((64, 210), f"出战 {battle_num} 次", font=get_font(22), fill=GRAY)
    draw.text((width - 70, 116), f"{stars}/{max_stars}", font=get_font(52), fill=GOLD, anchor="ra")
    draw.text((width - 72, 174), "星数", font=get_font(22), fill=GRAY, anchor="ra")

    if not has_data:
        paste_panel(img, (70, 330, width - 70, 560), radius=20, fill=(255, 255, 255, 220))
        draw = ImageDraw.Draw(img)
        draw.text((width // 2, 420), f"暂无{title}挑战数据", font=get_font(30), fill=FIRST, anchor="mm")
        draw.text((width // 2, 468), "开放数据后即可生成战绩卡", font=get_font(22), fill=MUTED, anchor="mm")
        return convert_img(img)

    star = load_rgba(sr_texture(module, "star.png"), (28, 28))
    star_gray = load_rgba(sr_texture(module, "star_gray.png"), (28, 28))

    y = head_h
    for floor in floors:
        paste_panel(img, (44, y, width - 44, y + floor_h - 22), radius=18, fill=(255, 255, 255, 220))
        draw = ImageDraw.Draw(img)
        name = str(getv(floor, "name", "--") or "--")
        floor_stars = _stars_for_floor(floor)
        text_fit(draw, (72, y + 24), name, 28, FIRST, 440)
        for i in range(3):
            icon = star if i < floor_stars else star_gray
            if icon:
                img.paste(icon, (width - 172 + i * 36, y + 22), icon)
            else:
                draw.text((width - 164 + i * 34, y + 20), "★" if i < floor_stars else "☆", font=get_font(24), fill=GOLD)

        for idx, node_key in enumerate(("node_1", "node_2")):
            node = getv(floor, node_key, None)
            x = 72 + idx * 390
            label = "上半" if idx == 0 else "下半"
            score = getv(node, "score", "") if node else ""
            draw.text((x, y + 72), f"{label}{f' · {score}' if score else ''}", font=get_font(20), fill=MUTED)
            chars = _node_chars(node) if node else []
            names = "、".join(_char_name(c) for c in chars[:4]) or "--"
            text_fit(draw, (x, y + 104), names, 23, FIRST, 340)
            ctime = date_text(getv(node, "challenge_time", None)) if node else ""
            if ctime and ctime != "--":
                text_fit(draw, (x, y + 140), ctime, 18, MUTED, 340)
        y += floor_h

    return convert_img(img)


async def render_forgotten_hall(data, uid: str, previous: bool = False) -> bytes:
    return await render_endgame(data, uid, "忘却之庭", previous, "starrailuid_abyss", PURPLE, 36)


async def render_pure_fiction(data, uid: str, previous: bool = False) -> bytes:
    return await render_endgame(data, uid, "虚构叙事", previous, "starrailuid_abyss_story", (222, 110, 235), 12)


async def render_apocalyptic_shadow(data, uid: str, previous: bool = False) -> bytes:
    return await render_endgame(data, uid, "末日幻影", previous, "starrailuid_abyss_boss", BLUE, 12)


async def render_challenge_peak(data, uid: str, previous: bool = False) -> bytes:
    period = "上期" if previous else "本期"
    records = listv(getv(data, "challenge_peak_records", []))
    best = getv(data, "challenge_peak_best_record_brief", None)
    width = 900
    height = 660 + max(0, len(records) - 1) * 210
    img = base_canvas(width, height, sr_texture("starrailuid_abyss_peak", "bg.jpg"))
    paste_panel(img, (34, 34, width - 34, 250), radius=20, fill=(22, 22, 34, 190))
    draw = ImageDraw.Draw(img)
    draw.text((64, 62), f"异相仲裁 · {period}", font=get_font(42), fill=RED)
    draw.text((64, 118), f"UID {uid}", font=get_font(22), fill=GRAY)
    if best:
        draw.text((64, 168), f"首领星数 {getv(best, 'boss_stars', 0)}", font=get_font(26), fill=WHITE)
        draw.text((300, 168), f"精英星数 {getv(best, 'mob_stars', 0)}", font=get_font(26), fill=WHITE)
        draw.text((width - 70, 126), f"{getv(best, 'total_battle_num', 0)}", font=get_font(52), fill=GOLD, anchor="ra")
        draw.text((width - 72, 184), "总战斗", font=get_font(22), fill=GRAY, anchor="ra")

    if not records:
        paste_panel(img, (70, 330, width - 70, 560), radius=20, fill=(255, 255, 255, 220))
        draw.text((width // 2, 430), "暂无异相仲裁数据", font=get_font(30), fill=FIRST, anchor="mm")
        return convert_img(img)

    y = 290
    for rec in records:
        group = getv(rec, "group", None)
        paste_panel(img, (44, y, width - 44, y + 180), radius=18, fill=(255, 255, 255, 220))
        draw = ImageDraw.Draw(img)
        title = getv(group, "name_mi18n", "挑战记录")
        draw.text((72, y + 24), str(title), font=get_font(28), fill=FIRST)
        draw.text((72, y + 70), f"首领 {getv(rec, 'boss_stars', 0)} 星 · 精英 {getv(rec, 'mob_stars', 0)} 星", font=get_font(24), fill=SECOND)
        draw.text((72, y + 112), f"战斗 {getv(rec, 'battle_num', 0)} 次", font=get_font(22), fill=MUTED)
        boss = getv(rec, "boss_info", None)
        if boss:
            draw.text((width - 72, y + 70), str(getv(boss, "name_mi18n", "")), font=get_font(24), fill=FIRST, anchor="ra")
        y += 210
    return convert_img(img)
