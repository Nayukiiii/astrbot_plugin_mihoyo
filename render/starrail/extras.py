from PIL import ImageDraw

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
    paste_panel,
    small_progress,
    sr_texture,
    stat_cell,
    text_fit,
)
from .grid_fight import render_grid_fight_card


async def render_monthly_award(data, uid: str, nickname: str = "") -> bytes:
    img = base_canvas(700, 1300, sr_texture("starrailuid_note", "monthly_bg.png"))
    draw = ImageDraw.Draw(img)
    month_data = getv(data, "month_data", None)
    day_data = getv(data, "day_data", None)
    draw.text((310, 184), nickname or getv(data, "uid", uid), font=get_font(34), fill=FIRST, anchor="lm")
    draw.text((267, 219), f"UID {uid}", font=get_font(20), fill=MUTED, anchor="lm")

    stat_cell(img, (72, 300, 330, 400), "今日星琼", str(getv(day_data, "current_hcoin", 0)), GOLD)
    stat_cell(img, (370, 300, 628, 400), "本月星琼", str(getv(month_data, "current_hcoin", 0)), GOLD)
    stat_cell(img, (72, 430, 330, 530), "今日票券", str(getv(day_data, "current_rails_pass", 0)), PURPLE)
    stat_cell(img, (370, 430, 628, 530), "本月票券", str(getv(month_data, "current_rails_pass", 0)), PURPLE)

    draw = ImageDraw.Draw(img)
    draw.text((72, 590), "收入构成", font=get_font(28), fill=FIRST)
    y = 640
    groups = listv(getv(month_data, "group_by", []))
    if not groups:
        draw.text((94, y), "暂无本月收入记录", font=get_font(22), fill=MUTED)
    for item in groups[:10]:
        name = str(getv(item, "action_name", getv(item, "action", "--")))
        num = int(getv(item, "num", 0) or 0)
        percent = int(getv(item, "percent", 0) or 0)
        text_fit(draw, (94, y), name, 22, FIRST, 310)
        draw.text((520, y), f"{num}", font=get_font(22), fill=FIRST, anchor="ra")
        draw.text((608, y), f"{percent}%", font=get_font(22), fill=MUTED, anchor="ra")
        small_progress(img, 94, y + 32, 510, percent, 100, GOLD)
        y += 68
    return convert_img(img)


async def render_sign_card(info, awards, uid: str, nickname: str = "") -> bytes:
    img = base_canvas(700, 900, sr_texture("starrailuid_help", "bg.jpg"))
    paste_panel(img, (44, 44, 656, 210), radius=20, fill=(22, 22, 34, 190))
    draw = ImageDraw.Draw(img)
    draw.text((72, 72), "星穹铁道签到", font=get_font(38), fill=GOLD)
    draw.text((72, 128), nickname or f"UID {uid}", font=get_font(24), fill=WHITE)
    draw.text((628, 118), "已签到" if getv(info, "is_sign", False) else "未签到", font=get_font(28), fill=GOLD, anchor="ra")
    stat_cell(img, (54, 250, 330, 350), "累计签到", f"{getv(info, 'total_sign_day', 0)} 天", GOLD)
    stat_cell(img, (370, 250, 646, 350), "漏签次数", f"{getv(info, 'sign_cnt_missed', 0)} 次", RED)

    draw = ImageDraw.Draw(img)
    draw.text((72, 400), "本月奖励", font=get_font(28), fill=WHITE)
    y = 450
    for award in listv(getv(awards, "awards", []))[:10]:
        paste_panel(img, (64, y, 636, y + 52), radius=12, fill=(255, 255, 255, 218))
        draw = ImageDraw.Draw(img)
        draw.text((86, y + 14), str(getv(award, "name", "--")), font=get_font(22), fill=FIRST)
        draw.text((612, y + 14), f"x{getv(award, 'cnt', 0)}", font=get_font(22), fill=MUTED, anchor="ra")
        y += 62
    return convert_img(img)


async def render_rogue_card(data, uid: str, previous: bool = False, floor: int | None = None) -> bytes:
    record = getv(data, "last_record", None) if previous else getv(data, "current_record", None)
    records = listv(getv(record, "records", []))
    title = "模拟宇宙"
    img = base_canvas(900, 620 + max(0, len(records) - 1) * 170, sr_texture("starrailuid_rogue", "bg.jpg"))
    paste_panel(img, (34, 34, 866, 230), radius=20, fill=(22, 22, 34, 190))
    draw = ImageDraw.Draw(img)
    draw.text((64, 64), title, font=get_font(42), fill=PURPLE)
    role = getv(data, "role", None)
    draw.text((64, 122), str(getv(role, "nickname", f"UID {uid}")), font=get_font(24), fill=WHITE)
    basic = getv(data, "basic_info", None)
    draw.text((64, 170), f"祝福 {getv(basic, 'unlocked_buff_num', 0)} · 奇物 {getv(basic, 'unlocked_miracle_num', 0)} · 技能点 {getv(basic, 'unlocked_skill_points', 0)}", font=get_font(22), fill=GRAY)

    if not records:
        paste_panel(img, (70, 310, 830, 520), radius=20, fill=(255, 255, 255, 220))
        draw.text((450, 410), "暂无模拟宇宙记录", font=get_font(30), fill=FIRST, anchor="mm")
        return convert_img(img)

    y = 270
    for rec in records[:6]:
        if floor and str(floor) not in str(getv(rec, "name", "")):
            continue
        paste_panel(img, (44, y, 856, y + 140), radius=18, fill=(255, 255, 255, 220))
        draw = ImageDraw.Draw(img)
        text_fit(draw, (72, y + 24), str(getv(rec, "name", "记录")), 28, FIRST, 420)
        draw.text((72, y + 72), f"分数 {getv(rec, 'score', 0)} · 难度 {getv(rec, 'difficulty', 0)} · 进度 {getv(rec, 'progress', 0)}", font=get_font(22), fill=SECOND)
        draw.text((832, y + 28), date_text(getv(rec, "finish_time", None)), font=get_font(18), fill=MUTED, anchor="ra")
        lineup = listv(getv(rec, "final_lineup", []))
        draw.text((72, y + 106), "阵容 " + "、".join(f"#{getv(c, 'id', '')} Lv.{getv(c, 'level', '')}" for c in lineup[:4]), font=get_font(20), fill=MUTED)
        y += 170
    return convert_img(img)


async def render_rogue_locust_card(data, uid: str) -> bytes:
    basic = getv(data, "basic", None)
    detail = getv(data, "detail", None)
    records = listv(getv(detail, "records", []))
    img = base_canvas(900, 620 + max(0, len(records) - 1) * 170, sr_texture("starrailuid_rogue", "bg.jpg"))
    paste_panel(img, (34, 34, 866, 230), radius=20, fill=(22, 22, 34, 190))
    draw = ImageDraw.Draw(img)
    draw.text((64, 64), "寰宇蝗灾", font=get_font(42), fill=GOLD)
    cnt = getv(basic, "cnt", None)
    draw.text((64, 132), f"区域 {getv(cnt, 'narrow', 0)} · 奇物 {getv(cnt, 'miracle', 0)} · 事件 {getv(cnt, 'event', 0)}", font=get_font(24), fill=WHITE)
    y = 270
    if not records:
        paste_panel(img, (70, 310, 830, 520), radius=20, fill=(255, 255, 255, 220))
        draw.text((450, 410), "暂无寰宇蝗灾记录", font=get_font(30), fill=FIRST, anchor="mm")
        return convert_img(img)
    for rec in records[:6]:
        paste_panel(img, (44, y, 856, y + 140), radius=18, fill=(255, 255, 255, 220))
        draw = ImageDraw.Draw(img)
        text_fit(draw, (72, y + 24), str(getv(rec, "name", "记录")), 28, FIRST, 420)
        draw.text((72, y + 72), f"难度 {getv(rec, 'difficulty', 0)} · 位面 {len(listv(getv(rec, 'blocks', [])))}", font=get_font(22), fill=SECOND)
        draw.text((832, y + 28), date_text(getv(rec, "finish_time", None)), font=get_font(18), fill=MUTED, anchor="ra")
        y += 170
    return convert_img(img)


async def render_role_index_card(data, uid: str, nickname: str = "") -> bytes:
    stats = getv(data, "stats", None)
    avatars = listv(getv(data, "avatar_list", []))
    rows = (len(avatars) + 3) // 4
    img = base_canvas(900, 360 + max(1, rows) * 150, sr_texture("starrailuid_roleinfo", "bg1.png"))
    paste_panel(img, (34, 34, 866, 250), radius=20, fill=(22, 22, 34, 190))
    draw = ImageDraw.Draw(img)
    draw.text((64, 64), nickname or "开拓者", font=get_font(42), fill=GOLD)
    draw.text((64, 122), f"UID {uid}", font=get_font(24), fill=WHITE)
    draw.text((64, 174), f"活跃 {getv(stats, 'active_days', 0)} 天 · 角色 {getv(stats, 'avatar_num', len(avatars))} · 成就 {getv(stats, 'achievement_num', 0)} · 忘却 {getv(stats, 'abyss_process', '--')}", font=get_font(22), fill=GRAY)
    y = 290
    for idx, avatar in enumerate(avatars):
        x = 44 + (idx % 4) * 214
        if idx and idx % 4 == 0:
            y += 150
        paste_panel(img, (x, y, x + 190, y + 120), radius=14, fill=(255, 255, 255, 220))
        draw = ImageDraw.Draw(img)
        text_fit(draw, (x + 18, y + 20), str(getv(avatar, "name", f"#{getv(avatar, 'id', '')}")), 23, FIRST, 140)
        draw.text((x + 18, y + 58), f"Lv.{getv(avatar, 'level', 0)}  命座 {getv(avatar, 'rank', 0)}", font=get_font(20), fill=MUTED)
        draw.text((x + 172, y + 58), "★" * int(getv(avatar, "rarity", 0) or 0), font=get_font(16), fill=GOLD, anchor="ra")
    return convert_img(img)
