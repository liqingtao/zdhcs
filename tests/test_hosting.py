# -*- coding: utf-8 -*-
"""托管能力测试：取消信号、窗口枚举、自动寻路。"""
from __future__ import annotations

import numpy as np
import pytest

from core.flow import Flow, FlowCancelled, FlowTimeout, ensure_on_page
from core import window as win
from run_juqing import run_juqing


def _blank_frame():
    return np.zeros((120, 200, 3), dtype=np.uint8)


def test_flow_wait_cancelled_immediately():
    fl = Flow(
        screenshot=_blank_frame,
        click=lambda *a, **k: None,
        should_stop=lambda: True,
    )
    with pytest.raises(FlowCancelled):
        fl.wait_for("whatever.png", timeout=5)


def test_flow_click_cancelled_immediately():
    fl = Flow(
        screenshot=_blank_frame,
        click=lambda *a, **k: None,
        should_stop=lambda: True,
    )
    with pytest.raises(FlowCancelled):
        fl.click_when_ready("whatever.png", timeout=5)


def test_flow_run_finishes_without_stop():
    noise_template = np.random.default_rng(3).integers(
        0, 255, (5, 5, 3), dtype=np.uint8
    )
    fl = Flow(
        screenshot=_blank_frame,
        click=lambda *a, **k: None,
        should_stop=lambda: False,
    )
    with pytest.raises(FlowTimeout):
        fl.wait_for(noise_template, timeout=0.3)


def test_list_windows_runs():
    result = win.list_windows()
    assert isinstance(result, list)
    for hwnd, title in result:
        assert isinstance(hwnd, int)
        assert isinstance(title, str) and title


def test_window_target_rejects_bad_hwnd():
    with pytest.raises(ValueError):
        win.WindowTarget(0xDEADBEEF)


def test_ensure_on_page_auto_nav(tmp_path):
    import cv2

    entry = np.random.default_rng(11).integers(0, 255, (30, 60, 3), dtype=np.uint8)
    entry_path = tmp_path / "entry.png"
    cv2.imwrite(str(entry_path), entry)
    nav = np.random.default_rng(12).integers(0, 255, (20, 40, 3), dtype=np.uint8)
    nav_path = tmp_path / "nav.png"
    cv2.imwrite(str(nav_path), nav)

    state = {"calls": 0, "nav_clicked": 0}
    clicks: list = []

    def screenshot():
        state["calls"] += 1
        frame = np.zeros((120, 200, 3), dtype=np.uint8)
        frame[5:25, 150:190] = nav  # 导航锚点一直可见
        if state["nav_clicked"] > 0 and state["calls"] > 1:
            frame[60:90, 20:80] = entry  # 寻路后入口锚点出现
        return frame

    def click(x, y):
        clicks.append((x, y))
        state["nav_clicked"] += 1

    fl = Flow(screenshot=screenshot, click=click, dry_run=False)
    result = ensure_on_page(
        fl,
        str(entry_path),
        nav_template=str(nav_path),
        entry_wait=1.0,
        nav_wait=3.0,
        tries=2,
        log=lambda *a: None,
    )
    assert result.found
    assert len(clicks) == 1
    assert clicks[0] == (170, 15)


def test_juqing_flow_cancelled_immediately():
    fl_calls = []
    logs: list = []
    run_juqing(
        rounds=1,
        dry_run=True,
        screenshot=_blank_frame,
        click=lambda x, y: fl_calls.append((x, y)),
        log=logs.append,
        should_stop=lambda: True,
    )
    assert not fl_calls
    assert any("取消" in line or "终止" in line for line in logs)


def test_juqing_flow_completes_one_step(tmp_path):
    """用合成画面验证新号剧情状态机走通一步。"""
    import cv2

    rng = np.random.default_rng(42)
    nav_tpl = rng.integers(0, 255, (20, 40, 3), dtype=np.uint8)
    nav_path = tmp_path / "nav_quest_npc.png"
    cv2.imwrite(str(nav_path), nav_tpl)

    dlg_tpl = rng.integers(0, 255, (15, 30, 3), dtype=np.uint8)
    dlg_path = tmp_path / "btn_dialog_continue.png"
    cv2.imwrite(str(dlg_path), dlg_tpl)

    confirm_tpl = rng.integers(0, 255, (15, 30, 3), dtype=np.uint8)
    confirm_path = tmp_path / "btn_dialog_confirm.png"
    cv2.imwrite(str(confirm_path), confirm_tpl)

    close_tpl = rng.integers(0, 255, (15, 30, 3), dtype=np.uint8)
    close_path = tmp_path / "btn_dialog_close.png"
    cv2.imwrite(str(close_path), close_tpl)

    battle_tpl = rng.integers(0, 255, (10, 20, 3), dtype=np.uint8)
    battle_path = tmp_path / "btn_enter_battle.png"
    cv2.imwrite(str(battle_path), battle_tpl)

    pickup_tpl = rng.integers(0, 255, (10, 20, 3), dtype=np.uint8)
    pickup_path = tmp_path / "btn_pickup.png"
    cv2.imwrite(str(pickup_path), pickup_tpl)

    # Patch juqing_config templates to use tmp_path
    import juqing_config as jq_cfg
    orig = dict(jq_cfg.TEMPLATES)
    jq_cfg.TEMPLATES.update({
        "nav_quest_npc": str(nav_path),
        "btn_dialog_continue": str(dlg_path),
        "btn_dialog_confirm": str(confirm_path),
        "btn_dialog_close": str(close_path),
        "btn_enter_battle": str(battle_path),
        "btn_pickup": str(pickup_path),
    })

    state = {"nav_clicked": 0, "dialog_clicked": 0}
    clicks: list = []
    logs: list = []

    def screenshot():
        frame = np.zeros((200, 300, 3), dtype=np.uint8)
        # 任务追踪 NPC 一直可见
        frame[5:25, 100:140] = nav_tpl
        # 第一次点 NPC 后对话出现
        if state["nav_clicked"] > 0 and state["dialog_clicked"] < 3:
            frame[60:75, 120:150] = dlg_tpl
        return frame

    def click(x, y):
        clicks.append((x, y))
        if 100 <= x <= 140 and 5 <= y <= 25:
            state["nav_clicked"] += 1
        elif 120 <= x <= 150 and 60 <= y <= 75:
            state["dialog_clicked"] += 1

    try:
        run_juqing(
            rounds=1,
            dry_run=False,
            screenshot=screenshot,
            click=click,
            log=logs.append,
            should_stop=lambda: False,
        )
    finally:
        jq_cfg.TEMPLATES.clear()
        jq_cfg.TEMPLATES.update(orig)

    assert state["nav_clicked"] >= 1
    assert state["dialog_clicked"] >= 1
    assert any("完成 1 步" in line for line in logs)
