"""第 3 步：用 Airtest 框架组织测试，学会 touch(Template(...))、assert_exists。

Airtest 需要连接真实设备（Android / Windows / iOS 等）才能截屏和点击，
所以真正跑起来前，请先按 README 装好依赖并准备好设备。可执行用例在
airtest_cases/smoke.air/smoke.py，真正运行交给 airtest_cases.run_airtest。

示例（装了 airtest 且连接设备后）：
    python -m demos.demo3_airtest --device Android:///
"""
import argparse

from airtest_cases import run_airtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Airtest 示例入口")
    parser.add_argument("--device", default="Android:///", help="Airtest 设备串")
    args = parser.parse_args()

    print("Airtest API 与我们低层原语的对应关系：")
    print("  touch(Template('btn.png'))        -> find_template() + click(center)")
    print("  assert_exists(Template('btn.png'))  -> find_template().found 为 True")
    print("  assert_equal(a, b)                -> 普通断言，失败会写进报告")
    print("  snapshot()                        -> 截图存证，附到报告里\n")

    try:
        import airtest  # noqa: F401
    except ImportError:
        print("当前环境未安装 airtest，无法真正运行用例。")
        print("请先: pip install -r requirements-airtest.txt")
        print("再运行: python -m airtest_cases.run_airtest --device Android:///")
        return

    raise SystemExit(run_airtest.run(args.device))


if __name__ == "__main__":
    main()


