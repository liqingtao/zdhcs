# -*- coding: utf-8 -*-
"""打图真实落地脚本：接真实屏幕，模板锚点驱动状态机 + 失败恢复。

支持两种运行方式：
1. CLI 直接跑：python run_datu.py --rounds 3 [--no-dry-run]
2. 被图形界面托管：注入 screenshot / click / log / should_stop，
   截图与点击只作用于托管窗口，「取消」随时安全停止。

流程：不在功能页面先自动寻路 -> 领取任务 -> 自动寻路 -> 战斗 -> 拾取 -> 交任务
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Callable, Optional

import config
import datu_config as cfg
from core import screen
from core.flow import Flow, FlowCancelled, FlowTimeout, ensure_on_page


def _evidence(fl: Flow, tag: str) -> Path:
    import cv2

    frame = fl.screenshot()
    path = config.LOG_DIR / f"datu_{tag}_{int(time.time())}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frame)
    return path


def _state_hint(fl: Flow, engine) -> str:
    """OCR 只做"现在大概在哪"的日志提示，不参与流程驱动。"""
    try:
        results = fl.read_text(engine=engine)
        text = "".join(r.text for r in results)
    except Exception:
        return "unknown"
    for state, keyword in cfg.STATE_KEYWORDS.items():
        if keyword in text:
            return state
    return "unknown"


def _do_step(fl: Flow, template, name: str, timeout: float, log) -> bool:
    """等锚点出现并点击；找不到返回 False 并留证。"""
    try:
        fl.click_when_ready(template, timeout=timeout)
        log(f"[步骤] {name} -> 点击")
        return True
    except FlowCancelled:
        raise
    except FlowTimeout:
        ev = _evidence(fl, name)
        log(f"[失败] {name}：等待超时，截图留证 {ev}")
        return False


def _real_click(x: int, y: int) -> None:
    """真正点击。screen.click 的 dry_run 默认值是 True，这里强制关掉。"""
    screen.click(x, y, dry_run=False)


def run_datu(
    rounds,
    dry_run: bool = True,
    screenshot=None,
    click: Optional[Callable[[int, int], None]] = None,
    log: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> None:
    """跑打图状态机。

    screenshot/click：画面与点击来源，被 GUI 托管时注入（打到托管窗口）。
    log：日志回调，默认 print。should_stop：返回 True 表示外部请求取消。
    """
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
    try:
        # 0. 确保在功能页面：不在就点导航锚点自动寻路。
        try:
            ensure_on_page(
                fl,
                cfg.TEMPLATES["btn_take_task"],
                nav_template=cfg.NAV_TEMPLATE,
                log=log,
            )
            log("[导航] 已进入打图页面")
        except FlowCancelled:
            raise
        except FlowTimeout as exc:
            ev = _evidence(fl, "not_on_page")
            log(f"[中止] 无法进入打图页面（截图留证 {ev}）：{exc}")
            return

        while completed < rounds:
            hint = _state_hint(fl, engine)
            log(f"\n===== 第 {completed + 1} 轮（OCR 提示: {hint}）=====")

            # 1. 领任务
            if not _do_step(fl, cfg.TEMPLATES["btn_take_task"], "领取任务", cfg.WAIT_TIMEOUT, log):
                break

            # 2. 自动寻路
            if not _do_step(fl, cfg.TEMPLATES["btn_auto_route"], "自动寻路", cfg.WAIT_TIMEOUT, log):
                break

            # 3. 等进入战斗（血条锚点出现）
            log("[步骤] 等待进入战斗…")
            try:
                fl.wait_for(cfg.TEMPLATES["btn_enter_battle"], timeout=cfg.BATTLE_TIMEOUT)
                log("[步骤] 已进入战斗")
            except FlowCancelled:
                raise
            except FlowTimeout:
                _evidence(fl, "enter_battle")
                log("[失败] 未等到进入战斗，跳过本轮")
                continue

            # 4. 等战斗结束（拾取按钮出现）
            log("[步骤] 等待战斗结束…")
            try:
                fl.wait_for(cfg.TEMPLATES["btn_pickup"], timeout=cfg.BATTLE_TIMEOUT)
                log("[步骤] 战斗结束")
            except FlowCancelled:
                raise
            except FlowTimeout:
                _evidence(fl, "battle_end")
                log("[失败] 未等到战斗结束，跳过本轮")
                continue

            # 5. 拾取
            if not _do_step(fl, cfg.TEMPLATES["btn_pickup"], "拾取", cfg.WAIT_TIMEOUT, log):
                continue

            # 6. 交任务
            if not _do_step(fl, cfg.TEMPLATES["btn_turnin"], "交任务", cfg.WAIT_TIMEOUT, log):
                continue

            completed += 1
            log(f"[完成] 第 {completed} 轮结束")
            fl.pause()
    except FlowCancelled:
        log("[取消] 收到停止请求，任务已终止")

    log(f"\n===== 结束，完成 {completed} 轮 =====")


def main() -> None:
    parser = argparse.ArgumentParser(description="打图自动化（真实屏幕）")
    parser.add_argument("--rounds", type=int, default=cfg.MAX_ROUNDS)
    parser.add_argument("--no-dry-run", action="store_true", help="真正点击鼠标")
    args = parser.parse_args()
    run_datu(args.rounds, dry_run=not args.no_dry_run)


if __name__ == "__main__":
    main()
