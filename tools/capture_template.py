# -*- coding: utf-8 -*-
"""从真实游戏画面截取按钮模板，是"图片识别点击"落地前的必要准备。

用法一：先截一张参考图（含你要的按钮），用于确定坐标。
    python -m tools.capture_template --shot ref.png

用法二：从参考图里按 (left, top, right, bottom) 裁出按钮，存为模板。
    python -m tools.capture_template --from ref.png --name btn_buy --box 200,260,360,330

用法三：直接截屏并裁出按钮（Windows 上常用）。
    python -m tools.capture_template --name btn_buy --box 200,260,360,330

模板默认存到 config.TEMPLATES_DIR，也就是 assets/templates/。裁剪只保存指定
区域，不改动原图；按钮尽量裁得"刚好包住"，不要带太多背景，否则阈值会掉。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2

import config
from core import matcher


def _parse_box(text: str):
    parts = [int(x.strip()) for x in text.split(",")]
    if len(parts) != 4:
        raise SystemExit("--box 需要 4 个整数：left,top,right,bottom")
    return tuple(parts)


def _shot(out_path: str) -> str:
    from core import screen

    frame = screen.screenshot(path=out_path)
    print(f"已截屏并保存: {out_path}（尺寸 {frame.shape[1]}x{frame.shape[0]}）")
    return str(out_path)


def _crop(src: str, name: str, box) -> str:
    img = matcher.load_image(src)
    left, top, right, bottom = box
    if not (0 <= left < right <= img.shape[1] and 0 <= top < bottom <= img.shape[0]):
        raise SystemExit(f"--box {box} 超出图片尺寸 {img.shape[1]}x{img.shape[0]}")
    template = img[top:bottom, left:right]
    out = config.TEMPLATES_DIR / name
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), template)
    print(f"模板已保存: {out}（尺寸 {template.shape[1]}x{template.shape[0]}）")
    return str(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="截取按钮模板")
    parser.add_argument("--shot", default=None, help="只截屏并保存到该路径（默认放 assets/screenshots/）")
    parser.add_argument("--from", dest="src", default=None, help="从已有图片裁剪，而不是新截屏")
    parser.add_argument("--name", default=None, help="模板文件名，如 btn_buy.png")
    parser.add_argument("--box", default=None, help="裁剪区域 left,top,right,bottom")
    args = parser.parse_args()

    if args.shot and args.name is None:
        out = args.shot
        if not Path(out).is_absolute():
            out = str(config.SCREENSHOTS_DIR / out)
        _shot(out)
        return

    if args.name is None or args.box is None:
        parser.error("裁剪模板需要同时提供 --name 和 --box（可选 --from 指定源图）")

    box = _parse_box(args.box)
    src = args.src if args.src else _shot(str(config.SCREENSHOTS_DIR / "capture_ref.png"))
    _crop(src, args.name, box)


if __name__ == "__main__":
    main()
