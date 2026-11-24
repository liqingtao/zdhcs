# -*- coding: utf-8 -*-
"""跑商真实落地脚本：接真实屏幕，OCR 读价 + 识别点击 + 状态机 + 失败恢复。

与打图/刷经验一样支持被 GUI 托管：注入 screenshot / click / log /
should_stop，截图与点击只作用于托管窗口，「取消」随时安全停止。

运行前：
1. 用 tools/capture_template.py 采集四个按钮模板到 assets/templates/。
2. 改 paoshang_config.py 里的 CITY_KEYWORDS，换成游戏里两个城市的 OCR 关键词。
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Callable, Optional

import config
import paoshang_config as cfg
from core import screen
from core.flow import Flow, FlowCancelled, FlowTimeout


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
        fl.check_stop()
        if _detect_city(fl, engine) == expect:
            return True
        fl.pause()
    return False


def _evidence(fl: Flow, tag: str) -> Path:
    """把当前画面存成证据截图，便于排查卡在哪一步。"""
    import cv2

    frame = fl.screenshot()
    path = config.LOG_DIR / f"paoshang_{tag}_{int(time.time())}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frame)
    return path


def _click_step(fl: Flow, template, name: str, log) -> bool:
    try:
        fl.click_when_ready(template, timeout=cfg.WAIT_TIMEOUT)
        log(f"[步骤] {name} -> 点击")
        return True
    except FlowCancelled:
        raise
    except FlowTimeout:
        ev = _evidence(fl, name)
        log(f"[失败] {name}：等待超时，截图留证 {ev}")
        return False


def _real_click(x: int, y: int) -> None:
    screen.click(x, y, dry_run=False)


def run_paoshang(
    rounds,
    dry_run: bool = True,
    screenshot=None,
    click: Optional[Callable[[int, int], None]] = None,
    log: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> None:
    from core.ocr import create_engine

    log = log or print
    engine = create_engine()
    fl = Flow(
        screenshot=screenshot or screen.screenshot,
        click=click or _real_click,
        threshold=cfg.THRESHOLD,
        method=cfg.METHOD,
        dry_run=dry_run,
        delay_range=cfg.DELAY_RANGE,
        should_stop=should_stop,
    )

    completed = 0
    unknown_streak = 0
    try:
        while completed < rounds:
            fl.check_stop()
            city = _detect_city(fl, engine)
            if city is None:
                unknown_streak += 1
                ev = _evidence(fl, "unknown")
                log(f"[状态] 认不出当前城市，截图留证 {ev}（{unknown_streak}/{cfg.UNKNOWN_STATE_RETRIES}）")
                if unknown_streak >= cfg.UNKNOWN_STATE_RETRIES:
                    log("[中止] 连续多次认不出城市，停止，请检查游戏是否在前台、CITY_KEYWORDS 是否配好。")
                    break
                fl.pause()
                continue
            unknown_streak = 0

            if city == "buy":
                price_results = _read_text(fl, engine, "买入价")
                prices = _numbers(price_results)
                price = prices[0] if prices else 0
                log(f"[买入城] 买入价 {price}")
                if price and price <= cfg.BUY_MAX_PRICE:
                    _click_step(fl, cfg.TEMPLATES["btn_buy"], "买入", log)
                    log("[买入城] 低价，已点击买入")
                else:
                    log("[买入城] 价格偏高，跳过买入")
                if _click_step(fl, cfg.TEMPLATES["btn_goto_sell"], "前往卖出城", log):
                    log("[买入城] 前往卖出城")
                    if _wait_city(fl, engine, "sell"):
                        log("[状态] 已到达卖出城")
                    else:
                        _evidence(fl, "goto_sell_fail")
                        log("[警告] 未能确认到达卖出城，继续下一轮检测")

            elif city == "sell":
                price_results = _read_text(fl, engine, "收购价")
                prices = _numbers(price_results)
                price = prices[0] if prices else 0
                log(f"[卖出城] 收购价 {price}")
                if price and price >= cfg.SELL_MIN_PRICE:
                    _click_step(fl, cfg.TEMPLATES["btn_sell"], "卖出", log)
                    log("[卖出城] 高价，已点击卖出")
                else:
                    log("[卖出城] 价格偏低，跳过卖出")
                if _click_step(fl, cfg.TEMPLATES["btn_goto_buy"], "返回买入城", log):
                    log("[卖出城] 返回买入城")
                    completed += 1
                    if _wait_city(fl, engine, "buy"):
                        log(f"[状态] 完成第 {completed} 轮，回到买入城")
                    else:
                        _evidence(fl, "goto_buy_fail")
                        log("[警告] 未能确认回到买入城，继续下一轮检测")

            fl.pause()
    except FlowCancelled:
        log("[取消] 收到停止请求，任务已终止")

    log(f"\n===== 结束，完成 {completed} 轮 =====")


def main() -> None:
    parser = argparse.ArgumentParser(description="跑商自动化（真实屏幕）")
    parser.add_argument("--rounds", type=int, default=cfg.MAX_ROUNDS)
    parser.add_argument("--no-dry-run", action="store_true", help="真正点击鼠标")
    args = parser.parse_args()
    run_paoshang(args.rounds, dry_run=not args.no_dry_run)


if __name__ == "__main__":
    main()
