"""第 2 步：OpenCV 模板匹配 + 阈值判断。

重点演示三件事：
1. 找到最佳匹配位置，并打印相似度；
2. 保存"相似度热力图"，直观看到按钮出现在画面哪里；
3. 扫一遍不同阈值，体会 threshold 怎么影响"到底算不算出现"。

示例：
    python -m demos.demo2_opencv
"""
import argparse

import config
from core import matcher


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenCV 模板匹配与阈值")
    parser.add_argument(
        "--screen",
        default=str(config.SCREENSHOTS_DIR / "fake_screen.png"),
    )
    parser.add_argument(
        "--template",
        default=str(config.TEMPLATES_DIR / "btn_start.png"),
    )
    parser.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD)
    args = parser.parse_args()

    result = matcher.find_template(args.screen, args.template, threshold=args.threshold)
    print(result)

    heat_path = config.SCREENSHOTS_DIR / "heatmap.png"
    matcher.save_heatmap(args.screen, args.template, heat_path, method=result.method)
    print(f"相似度热力图 -> {heat_path}")

    annotated_path = config.SCREENSHOTS_DIR / "matched.png"
    matcher.annotate(args.screen, result, out_path=annotated_path)
    print(f"匹配框标注图 -> {annotated_path}")

    print("\n阈值扫描（相同模板，只改 threshold）：")
    for t in (0.60, 0.75, 0.85, 0.95, 1.00):
        r = matcher.find_template(args.screen, args.template, threshold=t)
        verdict = "命中" if r.found else "未命中"
        print(f"  threshold={t:.2f} -> {verdict}, confidence={r.confidence:.4f}")


if __name__ == "__main__":
    main()

