# -*- coding: utf-8 -*-
"""生成刷经验的假画面和按钮模板，供离线演示"开始->战斗->领取经验->继续"的状态机。

三个状态各一张画面，加上进入战斗的锚点（血条）等模板。按钮样式固定，
模板匹配几乎满分，便于先跑通状态机逻辑再接真实屏幕。
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import config
from demos.make_fake_screen import _cjk_font, _centered_text, _rounded_box


W, H = config.FAKE_SCREEN_SIZE


def _render(state: str, round_no: int) -> Image.Image:
    img = Image.new("RGB", (W, H), (24, 28, 46))
    draw = ImageDraw.Draw(img)
    title_font = _cjk_font(32)
    text_font = _cjk_font(26)
    btn_font = _cjk_font(24)

    titles = {
        "idle": "刷经验 · 待命",
        "battle": "刷经验 · 战斗中",
        "reward": "刷经验 · 战斗结束",
    }
    draw.text((W // 2, 40), titles[state], font=title_font, fill=(240, 240, 245), anchor="mm")

    if state == "idle":
        draw.text((W // 2, 130), "准备挂机刷怪", font=text_font, fill=(170, 210, 240), anchor="mm")
        _rounded_box(draw, (250, 250, 550, 330), radius=12, fill=(36, 140, 84), outline=(120, 230, 160))
        _centered_text(draw, (250, 250, 550, 330), "开始刷怪", btn_font, (255, 255, 255))

    elif state == "battle":
        # 血条锚点：进入战斗的标志。
        _rounded_box(draw, (140, 140, 660, 200), radius=10, fill=(60, 22, 22), outline=(200, 60, 60))
        _rounded_box(draw, (150, 150, 470, 190), radius=8, fill=(180, 50, 50), outline=(230, 120, 120))
        draw.text((W // 2, 260), "自动战斗中，请勿关闭…", font=text_font, fill=(255, 180, 120), anchor="mm")

    elif state == "reward":
        draw.text((W // 2, 120), "获得 经验 +9999", font=text_font, fill=(140, 220, 160), anchor="mm")
        _rounded_box(draw, (200, 250, 360, 330), radius=12, fill=(178, 104, 32), outline=(250, 200, 120))
        _centered_text(draw, (200, 250, 360, 330), "领取经验", btn_font, (255, 255, 255))
        _rounded_box(draw, (440, 250, 600, 330), radius=12, fill=(36, 140, 84), outline=(120, 230, 160))
        _centered_text(draw, (440, 250, 600, 330), "继续挑战", btn_font, (255, 255, 255))

    draw.text((W // 2, 460), f"第 {round_no} 轮", font=text_font, fill=(120, 130, 150), anchor="mm")
    return img


def _to_bgr(img: Image.Image) -> np.ndarray:
    import cv2

    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def make_templates() -> dict:
    """从三张假画面裁出四个锚点模板。"""
    idle = _render("idle", 1)
    battle = _render("battle", 1)
    reward = _render("reward", 1)
    return {
        "btn_start_grind": str(_save(idle, (250, 250, 550, 330), "btn_start_grind.png")),
        "btn_enter_battle": str(_save(battle, (150, 150, 470, 190), "btn_enter_battle.png")),
        "btn_collect_xp": str(_save(reward, (200, 250, 360, 330), "btn_collect_xp.png")),
        "btn_continue": str(_save(reward, (440, 250, 600, 330), "btn_continue.png")),
    }


def _save(img: Image.Image, box, name: str) -> str:
    path = config.TEMPLATES_DIR / name
    img.crop(box).save(path)
    return str(path)


def save_scenes(round_no: int = 1) -> dict:
    """保存三张静态画面供肉眼核对。"""
    out = {}
    for state in ("idle", "battle", "reward"):
        p = config.SCREENSHOTS_DIR / f"shuajingyan_{state}.png"
        _render(state, round_no).save(p)
        out[state] = str(p)
    return out


if __name__ == "__main__":
    t = make_templates()
    s = save_scenes()
    print("模板:", *t.values(), sep="\n  ")
    print("画面:", *s.values(), sep="\n  ")
