# -*- coding: utf-8 -*-
"""刷经验真实落地脚本：接真实屏幕，模板锚点驱动循环状态机 + 失败恢复。

刷经验是"挂机刷怪"循环：开始刷怪 -> 进入战斗(血条) -> 战斗结束(领取经验)
-> 继续挑战 -> 下一轮。支持被 GUI 托管：注入 screenshot / click / log /
should_stop；不在功能页面时先点导航锚点自动寻路。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Callable, Optional

import config
import shuajingyan_config as cfg
from core import screen
from core.flow import Flow, FlowCancelled, FlowTimeout, ensure_on_page


def _evidence(fl: Flow, tag: str) -> Path:
    import cv2

    frame = fl.screenshot()
    path = config.LOG_DIR / f"shuajingyan_{tag}_{int(time.time())}.png"
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
    screen.click(x, y, dry_run=False)


def run_shuajingyan(
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
    try:
        # 0. 确保在功能页面：不在就点导航锚点自动寻路。
        try:
            ensure_on_page(
                fl,
                cfg.TEMPLATES["btn_start_grind"],
                nav_template=cfg.NAV_TEMPLATE,
                log=log,
            )
            log("[导航] 已进入刷经验页面")
        except FlowCancelled:
            raise
        except FlowTimeout as exc:
            ev = _evidence(fl, "not_on_page")
            log(f"[中止] 无法进入刷经验页面（截图留证 {ev}）：{exc}")
            return

        # 开场：点"开始刷怪"进入第一次战斗，找不到就退出。
        if not _do_step(fl, cfg.TEMPLATES["btn_start_grind"], "开始刷怪", cfg.WAIT_TIMEOUT, log):
            log("[中止] 未找到\"开始刷怪\"按钮，请检查游戏是否在前台、模板是否采集正确。")
            return

        while completed < rounds:
            log(f"\n===== 第 {completed + 1} 轮 =====")
            hint = _state_hint(fl, engine)
            log(f"[状态] 当前 OCR 提示: {hint}")

            # 1. 等进入战斗（血条锚点出现）
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

            # 2. 等战斗结束（领取经验按钮出现）
            log("[步骤] 等待战斗结束…")
            try:
                fl.wait_for(cfg.TEMPLATES["btn_collect_xp"], timeout=cfg.BATTLE_TIMEOUT)
                log("[步骤] 战斗结束")
            except FlowCancelled:
                raise
            except FlowTimeout:
                _evidence(fl, "battle_end")
                log("[失败] 未等到战斗结束，跳过本轮")
                continue

            # 3. 领取经验
            if not _do_step(fl, cfg.TEMPLATES["btn_collect_xp"], "领取经验", cfg.WAIT_TIMEOUT, log):
                continue

            # 4. 继续挑战（下一轮）
            if not _do_step(fl, cfg.TEMPLATES["btn_continue"], "继续挑战", cfg.WAIT_TIMEOUT, log):
                continue

            completed += 1
            log(f"[完成] 第 {completed} 轮结束")
            fl.pause()
    except FlowCancelled:
        log("[取消] 收到停止请求，任务已终止")

    log(f"\n===== 结束，完成 {completed} 轮 =====")


def main() -> None:
    parser = argparse.ArgumentParser(description="刷经验自动化（真实屏幕）")
    parser.add_argument("--rounds", type=int, default=cfg.MAX_ROUNDS)
    parser.add_argument("--no-dry-run", action="store_true", help="真正点击鼠标")
    args = parser.parse_args()
    run_shuajingyan(args.rounds, dry_run=not args.no_dry_run)


if __name__ == "__main__":
    main()
