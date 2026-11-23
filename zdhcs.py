"""zdhcs 命令行入口：把桌面自动化测试能力打成一个可执行工具。

子命令：
  selftest   自检 OpenCV 模板匹配是否正常（离线，无 GUI）
  generate   生成假游戏画面和按钮模板
  find       在一张画面里找模板，打印命中位置/置信度
  click      截图 -> 找图 -> 点击（PyAutoGUI）
  ocr        用 OCR 读一张图里的文字
  airtest    自检 Airtest 是否可用（Template.match_in，离线）

用途：作为 PyInstaller 打包 Windows exe 的统一入口。OCR 与 Airtest 两个重依赖
会一并打进包里（OCR 用 RapidOCR/onnxruntime，Airtest 用 airtest+pocoui）。
"""
from __future__ import annotations

import argparse
import sys

import config


def _cmd_selftest(args: argparse.Namespace) -> int:
    import numpy as np

    from core.matcher import find_template

    rng = np.random.default_rng(0)
    screen = rng.integers(20, 80, (150, 200), dtype=np.uint8)
    pattern = np.random.default_rng(123).integers(30, 255, (30, 40), dtype=np.uint8)
    screen[40:70, 50:90] = pattern

    result = find_template(screen, pattern, threshold=0.85)
    ok = result.found and result.location == (50, 40)
    print("OpenCV 模板匹配自检:", "通过" if ok else "失败")
    print(result)
    return 0 if ok else 1


def _cmd_generate(args: argparse.Namespace) -> int:
    from demos.make_fake_screen import main as generate

    generate()
    return 0


def _cmd_find(args: argparse.Namespace) -> int:
    from core import matcher

    screen = matcher.load_image(args.screen)
    result = matcher.find_template(
        screen,
        args.template,
        threshold=args.threshold,
        method=args.method,
    )
    print(result)
    if result.found and args.out:
        matcher.annotate(screen, result, out_path=args.out)
        print("已保存标注图:", args.out)
    return 0 if result.found else 1


def _cmd_click(args: argparse.Namespace) -> int:
    from core import matcher, screen

    if args.screen:
        frame = matcher.load_image(args.screen)
        print(f"[demo] 使用本地画面: {args.screen}")
    else:
        frame = screen.screenshot(path=config.SCREENSHOTS_DIR / "live_screen.png")
        print(f"[demo] 已截取屏幕并保存到 {config.SCREENSHOTS_DIR / 'live_screen.png'}")

    result = matcher.find_template(frame, args.template, threshold=args.threshold)
    print(result)
    if not result.found:
        print("未找到目标按钮：可降低 --threshold，或检查模板与当前分辨率是否一致。")
        return 1

    x, y = result.center
    screen.click(x, y, dry_run=not args.no_dry_run, button=args.button)
    return 0


def _cmd_ocr(args: argparse.Namespace) -> int:
    from core import matcher
    from core.ocr import create_engine

    img = matcher.load_image(args.image)
    try:
        engine = create_engine()
        results = engine.read_text(img)
    except ImportError as exc:
        print(exc)
        print("提示：请安装 PaddleOCR 或 rapidocr_onnxruntime 之一，或从源码运行。")
        return 2

    for item in results:
        print(item)
    if args.keyword:
        hits = [r for r in results if args.keyword in r.text]
        print(f"\n关键词 {args.keyword!r} 命中 {len(hits)} 处")
        for r in hits:
            print(f"  {r}")
    return 0


def _cmd_airtest(args: argparse.Namespace) -> int:
    from core import matcher

    try:
        from airtest.core.api import Template
    except ImportError as exc:
        print("未安装 airtest，无法运行。请先: pip install -r requirements-airtest.txt")
        return 2

    screen = matcher.load_image(args.screen)
    template = Template(str(args.template), threshold=args.threshold)
    try:
        hit = template.match_in(screen)
    except Exception as exc:  # Airtest 对失败形态的封装较薄，统一转成可读错误
        print(f"Airtest 匹配出错: {exc}")
        return 1

    if hit is None:
        print("未命中：Airtest Template.match_in 返回空。")
        return 1

    print(f"Airtest 命中，点击坐标 {hit}（对应 assert_exists 为真）")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zdhcs",
        description="桌面/游戏自动化测试 CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_self = sub.add_parser("selftest", help="自检 OpenCV 模板匹配")
    p_self.set_defaults(func=_cmd_selftest)

    p_gen = sub.add_parser("generate", help="生成假游戏画面和按钮模板")
    p_gen.set_defaults(func=_cmd_generate)

    p_find = sub.add_parser("find", help="在画面里找模板")
    p_find.add_argument("--screen", required=True)
    p_find.add_argument("--template", required=True)
    p_find.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD)
    p_find.add_argument("--method", default=config.DEFAULT_METHOD)
    p_find.add_argument("--out", default=None, help="命中后保存标注图的路径")
    p_find.set_defaults(func=_cmd_find)

    p_click = sub.add_parser("click", help="截图 -> 找图 -> 点击")
    p_click.add_argument("--screen", default=None, help="本地图片；不传则截真实屏幕")
    p_click.add_argument("--template", default=str(config.TEMPLATES_DIR / "btn_start.png"))
    p_click.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD)
    p_click.add_argument("--button", default="left", choices=("left", "right", "middle"))
    p_click.add_argument("--no-dry-run", action="store_true", help="真正点击")
    p_click.set_defaults(func=_cmd_click)

    p_ocr = sub.add_parser("ocr", help="读图里的文字")
    p_ocr.add_argument("--image", required=True)
    p_ocr.add_argument("--keyword", default=None)
    p_ocr.set_defaults(func=_cmd_ocr)

    p_air = sub.add_parser("airtest", help="Airtest Template.match_in 自检")
    p_air.add_argument("--screen", required=True)
    p_air.add_argument("--template", default=str(config.TEMPLATES_DIR / "btn_start.png"))
    p_air.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD)
    p_air.set_defaults(func=_cmd_airtest)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

