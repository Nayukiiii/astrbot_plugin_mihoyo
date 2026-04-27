from PIL import Image, ImageDraw

from .common import (
    BLUE,
    FIRST,
    GOLD,
    MUTED,
    PURPLE,
    RED,
    SECOND,
    WHITE,
    base_canvas,
    convert_img,
    get_font,
    getv,
    hhmm_cn,
    load_rgba,
    paste_panel,
    seconds,
    small_progress,
    sr_texture,
    stat_cell,
    text_fit,
)


def _note_bg() -> Image.Image:
    bg = load_rgba(sr_texture("starrailuid_stamina", "note_bg.png"))
    if bg:
        return bg
    return base_canvas(700, 1200).convert("RGBA")


def _draw_ring(img: Image.Image, percent: float) -> None:
    ring_path = sr_texture("starrailuid_stamina", "ring.apng")
    if not ring_path:
        return
    try:
        ring = Image.open(ring_path)
        ring.seek(min(89, max(0, round(percent * 89))))
        ring = ring.convert("RGBA")
        img.paste(ring, (0, 5), ring)
    except Exception:
        return


async def render_starrail_notes(notes, uid: str, nickname: str = "", level: int | str = "") -> bytes:
    """StarRailUID 风格实时便笺。按真实 note/widget 字段绘制，不展示派遣。"""
    img = _note_bg()
    draw = ImageDraw.Draw(img)

    stamina = int(getv(notes, "current_stamina", 0) or 0)
    max_stamina = int(getv(notes, "max_stamina", 240) or 240)
    stamina_percent = stamina / max_stamina if max_stamina else 0
    recover_sec = seconds(getv(notes, "stamina_recover_time", 0))
    stamina_color = RED if stamina_percent >= 0.8 else SECOND

    _draw_ring(img, stamina_percent)

    draw.text((350, 139), nickname or "开拓者", font=get_font(36), fill=WHITE, anchor="mm")
    subtitle = "崩坏：星穹铁道"
    if level not in ("", None):
        subtitle = f"开拓等级 {level}"
    draw.text((350, 190), subtitle, font=get_font(24), fill=WHITE, anchor="mm")
    draw.text((350, 450), f"{stamina}/{max_stamina}", font=get_font(50), fill=FIRST, anchor="mm")
    draw.text((350, 490), f"还剩{hhmm_cn(recover_sec)}", font=get_font(24), fill=stamina_color, anchor="mm")
    draw.text((350, 663), f"UID{uid}", font=get_font(26), fill=FIRST, anchor="mm")

    reserve = int(getv(notes, "current_reserve_stamina", 0) or 0)
    if reserve:
        full = bool(getv(notes, "is_reserve_stamina_full", False))
        color = RED if full else SECOND
        draw.text((350, 535), f"备用开拓力 {reserve}", font=get_font(22), fill=color, anchor="mm")

    train = int(getv(notes, "current_train_score", 0) or 0)
    train_max = int(getv(notes, "max_train_score", 500) or 500)
    rogue = int(getv(notes, "current_rogue_score", 0) or 0)
    rogue_max = int(getv(notes, "max_rogue_score", 14000) or 14000)
    tourn_unlocked = bool(getv(notes, "rogue_tourn_weekly_unlocked", False))
    tourn_cur = int(getv(notes, "rogue_tourn_weekly_cur", 0) or 0)
    tourn_max = int(getv(notes, "rogue_tourn_weekly_max", 0) or 0)

    score_items = [("每日实训", f"{train}/{train_max}"), ("模拟宇宙", f"{rogue}/{rogue_max}")]
    if tourn_unlocked or tourn_max:
        score_items.append(("差分宇宙", f"{tourn_cur}/{tourn_max}"))
    score_xs = (175, 350, 525) if len(score_items) >= 3 else (260, 440)
    for index, (label, value) in enumerate(score_items):
        x = score_xs[index]
        draw.text((x, 694), label, font=get_font(18), fill=SECOND, anchor="mm")
        draw.text((x, 720), value, font=get_font(20), fill=FIRST, anchor="mm")

    # 覆盖原 StarRailUID 派遣区，改成真实便笺状态面板。
    overlay = Image.new("RGBA", (700, 420), (255, 251, 242, 232))
    img.paste(overlay, (0, 760), overlay)
    draw = ImageDraw.Draw(img)
    draw.text((52, 790), "实时便笺", font=get_font(28), fill=FIRST)
    draw.text((648, 794), "MiHoYo APP", font=get_font(18), fill=MUTED, anchor="ra")

    stat_cell(img, (44, 838, 330, 938), "每日实训", f"{train}/{train_max}", PURPLE)
    small_progress(img, 62, 918, 230, train, train_max, PURPLE)
    stat_cell(img, (370, 838, 656, 938), "模拟宇宙", f"{rogue}/{rogue_max}", BLUE)
    small_progress(img, 388, 918, 230, rogue, rogue_max, BLUE)

    if tourn_unlocked or tourn_max:
        stat_cell(img, (44, 966, 330, 1066), "差分宇宙", f"{tourn_cur}/{tourn_max}", GOLD)
        small_progress(img, 62, 1046, 230, tourn_cur, tourn_max, GOLD)
    else:
        stat_cell(img, (44, 966, 330, 1066), "差分宇宙", "未解锁", MUTED)

    cocoon_cnt = int(getv(notes, "weekly_cocoon_cnt", 0) or 0)
    cocoon_limit = int(getv(notes, "weekly_cocoon_limit", 3) or 3)
    sign_text = "已签到" if bool(getv(notes, "has_signed", False)) else "待确认"
    stat_cell(img, (370, 966, 656, 1066), "周本 / 签到", f"{cocoon_cnt}/{cocoon_limit}", FIRST, sign_text)
    small_progress(img, 388, 1046, 230, cocoon_cnt, cocoon_limit, GOLD)

    paste_panel(img, (44, 1092, 656, 1152), radius=16, fill=(255, 255, 255, 210))
    draw = ImageDraw.Draw(img)
    recovery = "已满" if recover_sec <= 0 else f"{hhmm_cn(recover_sec)}后回满"
    text_fit(draw, (64, 1112), recovery, 24, FIRST, 430)
    draw.text((636, 1114), "实时刷新", font=get_font(20), fill=MUTED, anchor="ra")

    return convert_img(img.convert("RGB"))
