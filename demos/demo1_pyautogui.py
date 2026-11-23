"""第 1 步：PyAutoGUI「截图 -> 找图 -> 点击」的最小闭环。

这里把 PyAutoGUI 当作"手"：负责截图和点击；把 OpenCV 当作"眼睛"：
负责判断按钮在哪。没有真实屏幕时，用 --screen 指定本地图片即可离线演示。

示例：
    python -m demos.demo1_pyautogui                    # 真实截屏 + 干跑点击
    python -m demos.demo1_pyautogui --screen assets/screenshots/fake_screen.png
    python -m demos.demo1_pyautogui --no-dry-run      # 真的点击（需要权限）
"""
import argparse

import config
from core import matcher, screen


def main() -> None:
    parser = argparse.ArgumentParser(description="PyAutoGUI 截图 -> 找图 -> 点击")
    parser.add_argument(
        "--screen",
        default=None,
        help="本地图片路径；不传则截取真实屏幕",
    )
    parser.add_argument(
        "--template",
        default=str(config.TEMPLATES_DIR / "btn_start.png"),
        help="按钮模板图路径",
    )
    parser.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD)
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="真正点击鼠标（默认只打印坐标，避免误触）",
    )
    args = parser.parse_args()

    if args.screen:
        frame = matcher.load_image(args.screen)
        print(f"[demo] 使用本地画面: {args.screen}")
    else:
        frame = screen.screenshot(path=config.SCREENSHOTS_DIR / "live_screen.png")
        print(f"[demo] 已截取真实屏幕并保存到 {config.SCREENSHOTS_DIR / 'live_screen.png'}")

    result = matcher.find_template(frame, args.template, threshold=args.threshold)
    print(result)

    if result.found:
        x, y = result.center
        screen.click(x, y, dry_run=not args.no_dry_run)
    else:
        print("未找到目标按钮：可降低 --threshold，或检查模板是否与当前分辨率/皮肤一致。")


if __name__ == "__main__":
    main()

