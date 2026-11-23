"""运行 .air 用例并生成 HTML 报告。

运行前会自动把 assets/templates 下的模板图同步进 .air 目录，
因为 Airtest 的 Template() 默认相对 .air 目录解析图片路径。

示例：
    python -m airtest_cases.run_airtest --device Android:///
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import config

CASE_DIR = config.ROOT / "airtest_cases" / "smoke.air"


def _sync_templates() -> None:
    for name in ("btn_start.png", "btn_reward.png"):
        src = config.TEMPLATES_DIR / name
        dst = CASE_DIR / name
        if src.exists():
            shutil.copy2(src, dst)
            print(f"[sync] {src.name} -> {dst}")


def run(device: str = "Android:///") -> int:
    _sync_templates()
    log_dir = config.LOG_DIR / "airtest"
    cmd = [
        sys.executable,
        "-m",
        "airtest",
        "run",
        str(CASE_DIR),
        "--device",
        device,
        "--log",
        str(log_dir),
    ]
    print("执行:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)

    try:
        from airtest.report.report import simple_report

        report_path = config.LOG_DIR / "report.html"
        simple_report(str(CASE_DIR), logpath=str(log_dir), output=str(report_path))
        print(f"HTML 报告 -> {report_path}")
    except Exception as exc:
        print(f"生成报告失败: {exc}")

    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 Airtest 用例并生成报告")
    parser.add_argument("--device", default="Android:///", help="Airtest 设备串")
    args = parser.parse_args()
    try:
        import airtest  # noqa: F401
    except ImportError:
        print("未安装 airtest，请先: pip install -r requirements-airtest.txt")
        raise SystemExit(1)
    raise SystemExit(run(args.device))


if __name__ == "__main__":
    main()

