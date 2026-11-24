# -*- coding: utf-8 -*-
"""跑商真实落地脚本：接真实屏幕，OCR 读价 + 识别点击 + 状态机 + 失败恢复。

运行前：
1. 用 tools/capture_template.py 采集四个按钮模板到 assets/templates/：
       btn_buy.png / btn_goto_sell.png / btn_sell.png / btn_goto_buy.png
2. 改 paoshang_config.py 里的 CITY_KEYWORDS，换成你游戏里两个城市的 OCR 关键词。
3. 先 --dry-run 看坐标和决策对不对，确认后再加 --no-dry-run。

用法：
    python run_paoshang.py --rounds 5                # 干跑（默认，只打印）
    python run_paoshang.py --rounds 5 --no-dry-run   # 真点
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import config
import paoshang_config as cfg
from core import matcher, screen
from core.flow import Flow


def _numbers(results) -> list[int]:
    nums: list[int] = []
    for r in results:
        for m in re.findall(r"\d{3,7}", r.text):
            nums.append(int(m))
    return nums


def _read_text(fl: Flow, engine, keyword: str):
    return fl.read_text(keyword=keyword, engine=engine)


def _detect_city(fl: Flow, engine) -> str | None:
    """用 OCR 判断当前在哪个城，认不出返回 None。"""
    for city, keyword in cfg.CITY_KEYWORDS.items():
        if _read_text(fl, engine, keyword):
            return city
    return None


def _wait_city(fl: Flow, engine, expect: str, timeout: float = cfg.WAIT_TIMEOUT) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _detect_city(fl, engine) == expect:
            return True
        fl.pause()
    return False


def _evidence(fl: Flow, tag: str) -> Path:
    """把当前画面存成证据截图，便于排查卡在哪一步。"""
    frame = fl.screenshot()
    path = config.LOG_DIR / f"paoshang_{tag}_{int(time.time())}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    import cv2

    cv2.imwrite(str(path), frame)
    return path


def _real_click(x: int, y: int) -> None:
    """真正点击。screen.click 的 dry_run 默认值是 True，这里强制关掉。"""
    screen.click(x, y, dry_run=False)


def run_paoshang(rounds: int, dry_run: bool = True) -> None:
    from core.ocr import create_engine

    engine = create_engine()
    fl = Flow(
        screenshot=screen.screenshot,
        click=_real_click,
        threshold=cfg.THRESHOLD,
        method=cfg.METHOD,
        dry_run=dry_run,
        delay_range=cfg.DELAY_RANGE,
    )

    completed = 0
    unknown_streak = 0

    while completed < rounds:
        city = _detect_city(fl, engine)
        if city is None:
            unknown_streak += 1
            ev = _evidence(fl, "unknown")
            print(f"[状态] 认不出当前城市，截图留证 {ev}（{unknown_streak}/{cfg.UNKNOWN_STATE_RETRIES}）")
            if unknown_streak >= cfg.UNKNOWN_STATE_RETRIES:
                print("[中止] 连续多次认不出城市，停止，请检查游戏是否在前台、CITY_KEYWORDS 是否配好。")
                break
            fl.pause()
            continue
        unknown_streak = 0

        if city == "buy":
            price_results = _read_text(fl, engine, "买入价")
            prices = _numbers(price_results)
            price = prices[0] if prices else 0
            print(f"[买入城] 买入价 {price}")
            if price and price <= cfg.BUY_MAX_PRICE:
                fl.click_when_ready(cfg.TEMPLATES["btn_buy"], timeout=cfg.WAIT_TIMEOUT)
                print(f"[买入城] 低价，已点击买入")
            else:
                print("[买入城] 价格偏高，跳过买入")
            fl.click_when_ready(cfg.TEMPLATES["btn_goto_sell"], timeout=cfg.WAIT_TIMEOUT)
            print("[买入城] 前往卖出城")
            if _wait_city(fl, engine, "sell"):
                print("[状态] 已到达卖出城")
            else:
                _evidence(fl, "goto_sell_fail")
                print("[警告] 未能确认到达卖出城，继续下一轮检测")

        elif city == "sell":
            price_results = _read_text(fl, engine, "收购价")
            prices = _numbers(price_results)
            price = prices[0] if prices else 0
            print(f"[卖出城] 收购价 {price}")
            if price and price >= cfg.SELL_MIN_PRICE:
                fl.click_when_ready(cfg.TEMPLATES["btn_sell"], timeout=cfg.WAIT_TIMEOUT)
                print(f"[卖出城] 高价，已点击卖出")
            else:
                print("[卖出城] 价格偏低，跳过卖出")
            fl.click_when_ready(cfg.TEMPLATES["btn_goto_buy"], timeout=cfg.WAIT_TIMEOUT)
            print("[卖出城] 返回买入城")
            completed += 1
            if _wait_city(fl, engine, "buy"):
                print(f"[状态] 完成第 {completed} 轮，回到买入城")
            else:
                _evidence(fl, "goto_buy_fail")
                print("[警告] 未能确认回到买入城，继续下一轮检测")

        fl.pause()

    print(f"\n===== 结束，完成 {completed} 轮 =====")


def main() -> None:
    parser = argparse.ArgumentParser(description="跑商自动化（真实屏幕）")
    parser.add_argument("--rounds", type=int, default=cfg.MAX_ROUNDS)
    parser.add_argument("--no-dry-run", action="store_true", help="真正点击鼠标")
    args = parser.parse_args()
    run_paoshang(args.rounds, dry_run=not args.no_dry_run)


if __name__ == "__main__":
    main()
