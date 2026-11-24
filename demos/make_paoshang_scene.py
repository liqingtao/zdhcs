# -*- coding: utf-8 -*-
"""生成跑商的假画面和按钮模板，方便离线演示"读价 -> 买卖 -> 跨城"闭环。

生成两张画面（买入城 / 卖出城）和四个按钮模板。按钮样式固定，模板匹配几乎满分，
价格用大字号，便于 RapidOCR 读数字。
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import config
from demos.make_fake_screen import _cjk_font, _centered_text, _rounded_box


W, H = config.FAKE_SCREEN_SIZE


def _render(city: str, price: int, goods: int, money: int) -> Image.Image:
    img = Image.new("RGB", (W, H), (28, 32, 52))
    draw = ImageDraw.Draw(img)
    title_font = _cjk_font(32)
    text_font = _cjk_font(26)
    btn_font = _cjk_font(24)

    title = "跑商 · 买入城" if city == "buy" else "跑商 · 卖出城"
    draw.text((W // 2, 40), title, font=title_font, fill=(240, 240, 245), anchor="mm")
    draw.text(
        (W // 2, 100),
        f"资金 {money}　货物 {goods}",
        font=text_font,
        fill=(160, 210, 240),
        anchor="mm",
    )

    if city == "buy":
        price_line = f"丝绸 买入价 {price}"
        price_color = (140, 220, 160) if price <= 9000 else (255, 170, 120)
    else:
        price_line = f"丝绸 收购价 {price}"
        price_color = (140, 220, 160) if price >= 11000 else (255, 170, 120)
    draw.text((W // 2, 160), price_line, font=_cjk_font(34), fill=price_color, anchor="mm")

    if city == "buy":
        _rounded_box(draw, (200, 260, 360, 330), radius=12, fill=(36, 140, 84), outline=(120, 230, 160))
        _centered_text(draw, (200, 260, 360, 330), "买入", btn_font, (255, 255, 255))
        _rounded_box(draw, (440, 260, 620, 330), radius=12, fill=(50, 90, 150), outline=(130, 180, 230))
        _centered_text(draw, (440, 260, 620, 330), "前往卖出城", btn_font, (255, 255, 255))
    else:
        _rounded_box(draw, (200, 260, 360, 330), radius=12, fill=(178, 104, 32), outline=(250, 200, 120))
        _centered_text(draw, (200, 260, 360, 330), "卖出", btn_font, (255, 255, 255))
        _rounded_box(draw, (440, 260, 620, 330), radius=12, fill=(50, 90, 150), outline=(130, 180, 230))
        _centered_text(draw, (440, 260, 620, 330), "返回买入城", btn_font, (255, 255, 255))

    return img


def _to_bgr(img: Image.Image) -> np.ndarray:
    import cv2

    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def _save_template(img: Image.Image, box, name: str):
    path = config.TEMPLATES_DIR / name
    img.crop(box).save(path)
    return path


def make_templates() -> dict:
    """从两城画面裁出四个按钮模板并保存。"""
    buy = _render("buy", 8500, 0, 100000)
    sell = _render("sell", 12000, 20, 100000)
    return {
        "btn_buy": str(_save_template(buy, (200, 260, 360, 330), "btn_buy.png")),
        "btn_goto_sell": str(_save_template(buy, (440, 260, 620, 330), "btn_goto_sell.png")),
        "btn_sell": str(_save_template(sell, (200, 260, 360, 330), "btn_sell.png")),
        "btn_goto_buy": str(_save_template(sell, (440, 260, 620, 330), "btn_goto_buy.png")),
    }


def save_scenes() -> dict:
    """保存买入城 / 卖出城两张静态画面，方便肉眼核对。"""
    buy_path = config.SCREENSHOTS_DIR / "paoshang_buy.png"
    sell_path = config.SCREENSHOTS_DIR / "paoshang_sell.png"
    _render("buy", 8500, 0, 100000).save(buy_path)
    _render("sell", 12000, 20, 100000).save(sell_path)
    return {"buy": str(buy_path), "sell": str(sell_path)}


if __name__ == "__main__":
    t = make_templates()
    s = save_scenes()
    print("按钮模板:", *t.values(), sep="\n  ")
    print("画面:", *s.values(), sep="\n  ")
