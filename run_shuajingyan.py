# -*- coding: utf-8 -*-
"""刷经验真实落地脚本：接真实屏幕，模板锚点驱动循环状态机 + 失败恢复。

刷经验是"挂机刷怪"循环，每一步靠"下一个锚点出现"推进：
    开始刷怪 -> 进入战斗(血条) -> 战斗结束(领取经验) -> 继续挑战 -> 下一轮

运行前：
1. 用 tools/capture_template.py 采集四个锚点模板到 assets/templates/：
       btn_start_grind / btn_enter_battle / btn_collect_xp / btn_continue
2. 先 --dry-run 看每一步点得对不对，确认后再 --no-dry-run。

用法：
    python run_shuajingyan.py --rounds 5                # 干跑（默认）
    python run_shuajingyan.py --rounds 5 --no-dry-run   # 真点
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import config
import shuajingyan_config as cfg
from core import screen
from core.flow import Flow, FlowTimeout


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


def _do_step(fl: Flow, template, name: str, timeout: float) -> bool:
    """等锚点出现并点击；找不到返回 False 并留证。"""
    try:
        fl.click_when_ready(template, timeout=timeout)
        print(f"[步骤] {name} -> 点击 {fl.dry_run and '(干跑)' or ''}")
        return True
    except FlowTimeout:
        ev = _evidence(fl, name)
        print(f"[失败] {name}：等待超时，截图留证 {ev}")
        return False


def _real_click(x: int, y: int) -> None:
    """真正点击。screen.click 的 dry_run 默认值是 True，这里强制关掉。"""
    screen.click(x, y, dry_run=False)


def run_shuajingyan(rounds: int, dry_run: bool = True) -> None:
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

    # 开场：点"开始刷怪"进入第一次战斗，找不到就退出。
    if not _do_step(fl, cfg.TEMPLATES["btn_start_grind"], "开始刷怪", cfg.WAIT_TIMEOUT):
        print("[中止] 未找到\"开始刷怪\"按钮，请检查游戏是否在前台、模板是否采集正确。")
        return

    completed = 0
    while completed < rounds:
        print(f"\n===== 第 {completed + 1} 轮 =====")
        hint = _state_hint(fl, engine)
        print(f"[状态] 当前 OCR 提示: {hint}")

        # 1. 等进入战斗（血条锚点出现）
        print("[步骤] 等待进入战斗…")
        try:
            fl.wait_for(cfg.TEMPLATES["btn_enter_battle"], timeout=cfg.BATTLE_TIMEOUT)
            print("[步骤] 已进入战斗")
        except FlowTimeout:
            _evidence(fl, "enter_battle")
            print("[失败] 未等到进入战斗，跳过本轮")
            continue

        # 2. 等战斗结束（领取经验按钮出现）
        print("[步骤] 等待战斗结束…")
        try:
            fl.wait_for(cfg.TEMPLATES["btn_collect_xp"], timeout=cfg.BATTLE_TIMEOUT)
            print("[步骤] 战斗结束")
        except FlowTimeout:
            _evidence(fl, "battle_end")
            print("[失败] 未等到战斗结束，跳过本轮")
            continue

        # 3. 领取经验
        if not _do_step(fl, cfg.TEMPLATES["btn_collect_xp"], "领取经验", cfg.WAIT_TIMEOUT):
            continue

        # 4. 继续挑战（下一轮）
        if not _do_step(fl, cfg.TEMPLATES["btn_continue"], "继续挑战", cfg.WAIT_TIMEOUT):
            continue

        completed += 1
        print(f"[完成] 第 {completed} 轮结束")
        fl.pause()

    print(f"\n===== 结束，完成 {completed} 轮 =====")


def main() -> None:
    parser = argparse.ArgumentParser(description="刷经验自动化（真实屏幕）")
    parser.add_argument("--rounds", type=int, default=cfg.MAX_ROUNDS)
    parser.add_argument("--no-dry-run", action="store_true", help="真正点击鼠标")
    args = parser.parse_args()
    run_shuajingyan(args.rounds, dry_run=not args.no_dry_run)


if __name__ == "__main__":
    main()
