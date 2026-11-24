"""生成一张假游戏画面和对应的按钮模板，方便在没有真实游戏的情况下离线演示。

这个脚本会：
1. 画一张带标题、按钮、状态文字、倒计时的假画面；
2. 把两个按钮单独裁出来，存成模板图（供 find_template 使用）。

跑一遍之后，demo1/demo2/demo4 都可以直接用这些产物，不需要真机。
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config


def _cjk_font(size: int) -> ImageFont.FreeTypeFont:
    """优先找系统中文字体（Windows -> macOS），找不到才退回 PIL 默认字体。"""
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def _rounded_box(draw: ImageDraw.ImageDraw, box, radius, fill, outline):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=3)


def _centered_text(draw: ImageDraw.ImageDraw, box, text, font, fill):
    x0, y0, x1, y1 = box
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    w, h = right - left, bottom - top
    draw.text(((x0 + x1 - w) / 2, (y0 + y1 - h) / 2), text, font=font, fill=fill)


def main() -> dict:
    w, h = config.FAKE_SCREEN_SIZE
    img = Image.new("RGB", (w, h), (24, 28, 48))
    draw = ImageDraw.Draw(img)

    title_font = _cjk_font(34)
    text_font = _cjk_font(24)
    btn_font = _cjk_font(26)

    draw.text((w // 2, 36), "梦幻西游 · 自动化测试 Demo", font=title_font, fill=(240, 240, 245), anchor="mm")

    draw.text((w // 2, 96), "状态：进行中", font=text_font, fill=(140, 220, 160), anchor="mm")
    draw.text((w // 2, 136), "倒计时 00:30", font=text_font, fill=(255, 210, 120), anchor="mm")

    # 两个按钮，坐标后面要用于裁剪模板。
    btn_start = (250, 240, 390, 310)
    btn_reward = (410, 240, 550, 310)
    _rounded_box(draw, btn_start, radius=12, fill=(36, 140, 84), outline=(120, 230, 160))
    _rounded_box(draw, btn_reward, radius=12, fill=(178, 104, 32), outline=(250, 200, 120))
    _centered_text(draw, btn_start, "开始任务", btn_font, (255, 255, 255))
    _centered_text(draw, btn_reward, "领取奖励", btn_font, (255, 255, 255))

    screen_path = config.SCREENSHOTS_DIR / "fake_screen.png"
    img.save(screen_path)

    # 裁出按钮做模板。注意：模板和画面是同一份像素，匹配时几乎会是满分。
    template_start = img.crop(btn_start)
    template_reward = img.crop(btn_reward)
    start_path = config.TEMPLATES_DIR / "btn_start.png"
    reward_path = config.TEMPLATES_DIR / "btn_reward.png"
    template_start.save(start_path)
    template_reward.save(reward_path)

    print(f"假画面 -> {screen_path}")
    print(f"模板1 -> {start_path}")
    print(f"模板2 -> {reward_path}")
    return {
        "screen": screen_path,
        "btn_start": start_path,
        "btn_reward": reward_path,
    }


if __name__ == "__main__":
    main()

