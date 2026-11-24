# -*- coding: utf-8 -*-
"""生成打图的假画面和按钮模板，供离线演示"接任务->寻路->战斗->拾取"的状态机。

四个状态各一张画面，加上进入战斗的锚点（血条）等模板。按钮样式固定，
模板匹配几乎满分，便于先跑通状态机逻辑再接真实屏幕。
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import config
from demos.make_fake_screen import _cjk_font, _centered_text, _rounded_box


W, H = config.FAKE_SCREEN_SIZE


def _render(state: str, round_no: int) -> Image.Image:
    img = Image.new("RGB", (W, H), (26, 30, 50))
    draw = ImageDraw.Draw(img)
    title_font = _cjk_font(32)
    text_font = _cjk_font(26)
    btn_font = _cjk_font(24)

    titles = {
        "task": "打图 · 任务大厅",
        "route": "打图 · 寻路中",
        "battle": "打图 · 战斗中",
        "reward": "打图 · 战斗结束",
    }
    draw.text((W // 2, 40), titles[state], font=title_font, fill=(240, 240, 245), anchor="mm")

    if state == "task":
        draw.text((W // 2, 130), "每日打图任务", font=text_font, fill=(170, 210, 240), anchor="mm")
        _rounded_box(draw, (250, 250, 550, 330), radius=12, fill=(36, 140, 84), outline=(120, 230, 160))
        _centered_text(draw, (250, 250, 550, 330), "领取任务", btn_font, (255, 255, 255))

    elif state == "route":
        draw.text((W // 2, 130), "自动寻路到目标点…", font=text_font, fill=(240, 210, 130), anchor="mm")
        _rounded_box(draw, (250, 250, 550, 330), radius=12, fill=(50, 90, 150), outline=(130, 180, 230))
        _centered_text(draw, (250, 250, 550, 330), "自动寻路", btn_font, (255, 255, 255))

    elif state == "battle":
        # 血条锚点：进入战斗的标志。
        _rounded_box(draw, (140, 140, 660, 200), radius=10, fill=(60, 22, 22), outline=(200, 60, 60))
        _rounded_box(draw, (150, 150, 470, 190), radius=8, fill=(180, 50, 50), outline=(230, 120, 120))
        draw.text((W // 2, 260), "与怪物战斗中…", font=text_font, fill=(255, 180, 120), anchor="mm")

    elif state == "reward":
        draw.text((W // 2, 120), "获得 藏宝图 x1", font=text_font, fill=(140, 220, 160), anchor="mm")
        _rounded_box(draw, (200, 250, 360, 330), radius=12, fill=(178, 104, 32), outline=(250, 200, 120))
        _centered_text(draw, (200, 250, 360, 330), "拾取", btn_font, (255, 255, 255))
        _rounded_box(draw, (440, 250, 600, 330), radius=12, fill=(36, 140, 84), outline=(120, 230, 160))
        _centered_text(draw, (440, 250, 600, 330), "交任务", btn_font, (255, 255, 255))

    draw.text((W // 2, 460), f"第 {round_no} 轮", font=text_font, fill=(120, 130, 150), anchor="mm")
    return img


def _to_bgr(img: Image.Image) -> np.ndarray:
    import cv2

    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def make_templates() -> dict:
    """从四张假画面裁出五个锚点模板。"""
    task = _render("task", 1)
    route = _render("route", 1)
    battle = _render("battle", 1)
    reward = _render("reward", 1)
    return {
        "btn_take_task": str(_save(task, (250, 250, 550, 330), "btn_take_task.png")),
        "btn_auto_route": str(_save(route, (250, 250, 550, 330), "btn_auto_route.png")),
        "btn_enter_battle": str(_save(battle, (150, 150, 470, 190), "btn_enter_battle.png")),
        "btn_pickup": str(_save(reward, (200, 250, 360, 330), "btn_pickup.png")),
        "btn_turnin": str(_save(reward, (440, 250, 600, 330), "btn_turnin.png")),
    }


def _save(img: Image.Image, box, name: str) -> str:
    path = config.TEMPLATES_DIR / name
    img.crop(box).save(path)
    return str(path)


def save_scenes(round_no: int = 1) -> dict:
    """保存四张静态画面供肉眼核对。"""
    out = {}
    for state in ("task", "route", "battle", "reward"):
        p = config.SCREENSHOTS_DIR / f"datu_{state}.png"
        _render(state, round_no).save(p)
        out[state] = str(p)
    return out


if __name__ == "__main__":
    t = make_templates()
    s = save_scenes()
    print("模板:", *t.values(), sep="\n  ")
    print("画面:", *s.values(), sep="\n  ")
