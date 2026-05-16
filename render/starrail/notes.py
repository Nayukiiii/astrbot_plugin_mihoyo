from PIL import Image, ImageDraw, ImageFilter

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


def _erase_expedition_title(img: Image.Image) -> None:
    box = (72, 732, 306, 792)
    patch = img.crop((box[0], box[1] + 118, box[2], box[3] + 118)).filter(
        ImageFilter.GaussianBlur(2)
    )
    mask = Image.new("L", (box[2] - box[0], box[3] - box[1]), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, mask.width, mask.height), radius=12, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(8))
    img.paste(patch, box[:2], mask)


def _status_card(
    img: Image.Image,
    xy: tuple[int, int, int, int],
    label: str,
    value: str,
    current: int,
    total: int,
    accent: tuple,
    sub: str = "",
) -> None:
    paste_panel(img, xy, radius=12, fill=(255, 255, 255, 188))
    draw = ImageDraw.Draw(img)
    x0, y0, x1, _ = xy
    draw.text((x0 + 18, y0 + 14), label, font=get_font(19), fill=SECOND)
    text_fit(draw, (x0 + 18, y0 + 43), value, 27, accent, x1 - x0 - 36)
    if sub:
        text_fit(draw, (x1 - 18, y0 + 18), sub, 17, MUTED, x1 - x0 - 36, anchor="ra")
    small_progress(img, x0 + 18, y0 + 74, x1 - x0 - 36, current, total, accent)


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

    # 覆盖原 StarRailUID 派遣区，改成真实便笺状态面板。
    _erase_expedition_title(img)
    draw = ImageDraw.Draw(img)
    left, gap, card_w = 72, 36, 260
    right = left + card_w + gap
    draw.text((left, 764), "实时便笺", font=get_font(28), fill=FIRST)
    draw.text((628, 768), "MiHoYo APP", font=get_font(18), fill=MUTED, anchor="ra")

    _status_card(img, (left, 812, left + card_w, 910), "每日实训", f"{train}/{train_max}", train, train_max, PURPLE)
    _status_card(img, (right, 812, right + card_w, 910), "模拟宇宙", f"{rogue}/{rogue_max}", rogue, rogue_max, BLUE)

    if tourn_unlocked or tourn_max:
        _status_card(img, (left, 936, left + card_w, 1034), "差分宇宙", f"{tourn_cur}/{tourn_max}", tourn_cur, tourn_max, GOLD)
    else:
        _status_card(img, (left, 936, left + card_w, 1034), "差分宇宙", "未解锁", 0, 1, MUTED)

    cocoon_cnt = int(getv(notes, "weekly_cocoon_cnt", 0) or 0)
    cocoon_limit = int(getv(notes, "weekly_cocoon_limit", 3) or 3)
    sign_text = "已签到" if bool(getv(notes, "has_signed", False)) else "待确认"
    _status_card(img, (right, 936, right + card_w, 1034), "周本 / 签到", f"{cocoon_cnt}/{cocoon_limit}", cocoon_cnt, cocoon_limit, GOLD, sign_text)

    paste_panel(img, (left, 1064, 628, 1140), radius=12, fill=(255, 255, 255, 188))
    draw = ImageDraw.Draw(img)
    recovery = "已满" if recover_sec <= 0 else f"{hhmm_cn(recover_sec)}后回满"
    text_fit(draw, (left + 18, 1090), recovery, 24, FIRST, 380)
    draw.text((610, 1094), "实时刷新", font=get_font(19), fill=MUTED, anchor="ra")

    return convert_img(img.convert("RGB"))
