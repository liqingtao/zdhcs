"""第 5 步：PaddleOCR 读画面里的文字（倒计时、任务状态等）。

示例：
    python -m demos.demo4_ocr --image assets/screenshots/fake_screen.png
    python -m demos.demo4_ocr --image assets/screenshots/fake_screen.png --keyword 00:30
"""
import argparse

import config
from core import matcher
from core.ocr import create_engine, find_text


def main() -> None:
    parser = argparse.ArgumentParser(description="PaddleOCR 文字识别")
    parser.add_argument(
        "--image",
        default=str(config.SCREENSHOTS_DIR / "fake_screen.png"),
        help="要识别的图片路径",
    )
    parser.add_argument(
        "--keyword",
        default=None,
        help="只查找包含该关键词的文字",
    )
    args = parser.parse_args()

    img = matcher.load_image(args.image)

    try:
        engine = create_engine()
        results = engine.read_text(img)
    except ImportError as exc:
        print(exc)
        print("提示：请先安装 PaddleOCR 或 rapidocr_onnxruntime（二选一）。")
        return

    print("识别结果：")
    for r in results:
        print(f"  {r}")

    if args.keyword:
        hits = find_text(img, args.keyword, engine=engine)
        print(f"\n关键词 {args.keyword!r} 命中 {len(hits)} 处")
        for r in hits:
            print(f"  {r}")


if __name__ == "__main__":
    main()

