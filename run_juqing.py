# -*- coding: utf-8 -*-
"""新号剧情真实落地脚本：接真实屏幕，模板锚点驱动线性流程 + 失败恢复。

支持两种运行方式：
1. CLI 直接跑：python run_juqing.py --steps 5 [--no-dry-run]
2. 被图形界面托管：注入 screenshot / click / log / should_stop，
   截图与点击只作用于托管窗口，「取消」随时安全停止。

流程：不在功能页面先点任务追踪 NPC 自动寻路 -> 对话推进（依次点
继续/确认/关闭）-> 如遇战斗等结束 -> 重复直到剧情完成。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Callable, Optional

import config
import juqing_config as cfg
from core import screen
from core.flow import Flow, FlowCancelled, FlowTimeout, ensure_on_page


def _evidence(fl: Flow, tag: str) -> Path:
    import cv2

    frame = fl.screenshot()
    path = config.LOG_DIR / f"juqing_{tag}_{int(time.time())}.png"
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
    import os

    if not os.path.exists(str(template)):
        log(f"[跳过] {name}：模板文件不存在 {template}")
        return False
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


def _click_dialogs(fl: Flow, log) -> int:
    """依次尝试点击对话按钮，返回点击次数。

    按 DIALOG_CLICK_ORDER 优先级依次找：找到哪个点哪个，点完继续找。
    直到所有模板在短时间内都找不到（对话结束）为止。
    """
    clicks = 0
    idle_count = 0
    import os

    # 只保留实际存在的模板，缺失的对话模板静默跳过。
    active_order = [
        key for key in cfg.DIALOG_CLICK_ORDER
        if os.path.exists(str(cfg.TEMPLATES[key]))
    ]
    if not active_order:
        log("[对话] 对话按钮模板均未采集，跳过对话阶段")
        return 0
    while idle_count < cfg.UNKNOWN_STATE_RETRIES:
        fl.check_stop()
        clicked_this_round = False
        for key in active_order:
            template = cfg.TEMPLATES[key]
            try:
                fl.click_when_ready(template, timeout=cfg.WAIT_TIMEOUT)
                log(f"[对话] {key} -> 点击（第 {clicks + 1} 次）")
                clicks += 1
                clicked_this_round = True
                fl.pause()
                break
            except FlowCancelled:
                raise
            except FlowTimeout:
                continue
        if clicked_this_round:
            idle_count = 0
        else:
            idle_count += 1
            if idle_count < cfg.UNKNOWN_STATE_RETRIES:
                fl.pause()
    return clicks


def _wait_battle(fl: Flow, log) -> bool:
    """如果出现战斗锚点，等战斗结束并拾取。返回 True 表示处理了战斗。"""
    import os

    battle_tpl = cfg.TEMPLATES["btn_enter_battle"]
    if not os.path.exists(str(battle_tpl)):
        return False
    try:
        fl.wait_for(battle_tpl, timeout=3.0)
        log("[步骤] 进入剧情战斗，等待战斗结束…")
    except FlowCancelled:
        raise
    except FlowTimeout:
        return False

    # 等拾取按钮出现（战斗结束标志）
    try:
        fl.wait_for(cfg.TEMPLATES["btn_pickup"], timeout=cfg.BATTLE_TIMEOUT)
        log("[步骤] 战斗结束")
    except FlowCancelled:
        raise
    except FlowTimeout:
        _evidence(fl, "battle_end_timeout")
        log("[警告] 等待战斗结束超时，继续尝试下一步")
        return True

    # 点击拾取
    try:
        fl.click_when_ready(cfg.TEMPLATES["btn_pickup"], timeout=cfg.WAIT_TIMEOUT)
        log("[步骤] 拾取 -> 点击")
    except FlowCancelled:
        raise
    except FlowTimeout:
        log("[提示] 拾取按钮未出现，跳过")
    return True


def _wait_for_dialog(
    fl: Flow,
    log,
    timeout: float = 120.0,
) -> bool:
    """等待对话按钮出现（用户手动走到 NPC 面前后触发）。

    轮询所有可用对话模板，任何一个出现就返回 True。
    """
    import os

    available = [
        (key, cfg.TEMPLATES[key])
        for key in cfg.DIALOG_CLICK_ORDER
        if os.path.exists(str(cfg.TEMPLATES[key]))
    ]
    if not available:
        log("[等待] 没有对话模板可检测，跳过等待阶段")
        return False

    deadline = time.time() + timeout
    log(f"[等待] 等待对话按钮出现（最多 {timeout:.0f} 秒，请手动走到 NPC 面前触发对话）…")
    while time.time() < deadline:
        fl.check_stop()
        for key, template in available:
            try:
                result = fl.find(template, threshold=cfg.THRESHOLD - 0.05)
                if result.found:
                    log(f"[检测] 对话按钮 {key} 出现！")
                    return True
            except FlowCancelled:
                raise
            except Exception:
                continue
        time.sleep(1.0)
    log("[等待] 超时未检测到对话按钮")
    return False


def _real_click(x: int, y: int) -> None:
    screen.click(x, y, dry_run=False)


def run_juqing(
    rounds,
    dry_run: bool = True,
    screenshot=None,
    click: Optional[Callable[[int, int], None]] = None,
    log: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> None:
    """跑新号剧情流程。

    rounds 表示最多执行多少个"点击 NPC → 寻路 → 对话"循环。
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
        import os

        # 0. 确保任务追踪可见：不在页面时点导航锚点自动寻路。
        try:
            nav_tpl = cfg.TEMPLATES["nav_quest_npc"]
            if not os.path.exists(str(nav_tpl)):
                log(f"[中止] 任务追踪模板不存在: {nav_tpl}，请用 tools/capture_template.py 采集")
                return
            ensure_on_page(
                fl,
                nav_tpl,
                nav_template=cfg.NAV_TEMPLATE,
                log=log,
            )
            log("[导航] 任务追踪已可见")
        except FlowCancelled:
            raise
        except FlowTimeout as exc:
            ev = _evidence(fl, "not_on_page")
            log(f"[中止] 无法找到任务追踪（截图留证 {ev}）：{exc}")
            return

        while completed < rounds:
            hint = _state_hint(fl, engine)
            log(f"\n===== 剧情第 {completed + 1} 步（OCR 提示: {hint}）=====")

            # 1. 先处理可能的战斗
            if _wait_battle(fl, log):
                fl.pause()

            # 2. 点任务追踪 NPC 名触发自动寻路
            if not _do_step(fl, cfg.TEMPLATES["nav_quest_npc"], "点击任务追踪 NPC", cfg.WAIT_TIMEOUT, log):
                log("[中止] 任务追踪 NPC 不可见，无法继续")
                break

            # 3. 等待自动寻路到达（对话按钮出现）
            log("[步骤] 等待自动寻路到达目标…")
            arrived = False
            available_dialogs = [
                key for key in ("btn_dialog_continue", "btn_dialog_confirm")
                if os.path.exists(str(cfg.TEMPLATES[key]))
            ]
            if available_dialogs:
                for key in available_dialogs:
                    try:
                        fl.wait_for(cfg.TEMPLATES[key], timeout=cfg.ROUTE_TIMEOUT)
                        arrived = True
                        log(f"[步骤] 已到达目标（{key} 可见）")
                        break
                    except FlowCancelled:
                        raise
                    except FlowTimeout:
                        continue
                # 半自动模式：寻路后没看到对话，可能角色没到 NPC，等待用户手动触发
                if not arrived:
                    arrived = _wait_for_dialog(fl, log, timeout=cfg.ROUTE_TIMEOUT)
            else:
                # 没有对话模板：半自动模式，等待用户手动走到 NPC 触发对话
                log("[提示] 对话按钮模板未采集；半自动模式：请手动走到 NPC 面前触发对话")
                arrived = True  # 跳过等待，直接进入下一步（用户可以手动操作）

            if not arrived:
                ev = _evidence(fl, "route_timeout")
                log(f"[警告] 寻路后未看到对话按钮，截图留证 {ev}")
                # 可能还在寻路，下一轮再试
                completed += 1
                continue

            # 4. 点击对话按钮直到对话结束
            dialog_clicks = _click_dialogs(fl, log)
            log(f"[对话] 共点击 {dialog_clicks} 次，对话推进完成")

            # 5. 对话结束后可能触发战斗
            if _wait_battle(fl, log):
                fl.pause()

            completed += 1
            log(f"[完成] 剧情第 {completed} 步结束")
            fl.pause()
    except FlowCancelled:
        log("[取消] 收到停止请求，任务已终止")

    log(f"\n===== 结束，完成 {completed} 步 =====")


def main() -> None:
    parser = argparse.ArgumentParser(description="新号剧情自动化（真实屏幕）")
    parser.add_argument("--rounds", type=int, default=cfg.MAX_STEPS)
    parser.add_argument("--no-dry-run", action="store_true", help="真正点击鼠标")
    args = parser.parse_args()
    run_juqing(args.rounds, dry_run=not args.no_dry_run)


if __name__ == "__main__":
    main()
