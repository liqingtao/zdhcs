# -*- coding: utf-8 -*-
"""验证 core.flow 的等待/点击/步骤表逻辑（纯 OpenCV，离线可跑）。"""

import numpy as np
import pytest

from core.flow import Flow, FlowTimeout, run_steps


def _pattern(w, h):
    return np.random.default_rng(7).integers(30, 255, (h, w), dtype=np.uint8)


def _make_frame(with_button=True):
    frame = np.random.default_rng(0).integers(20, 80, (150, 200), dtype=np.uint8)
    if with_button:
        frame[40:70, 50:90] = _pattern(40, 30)
    return frame


def test_wait_for_finds_button_immediately():
    frame = _make_frame()
    template = frame[40:70, 50:90].copy()
    flow = Flow(screenshot=lambda: frame, click=lambda x, y: None, dry_run=True)

    result = flow.wait_for(template, timeout=2.0, interval=0.1)

    assert result.found is True
    assert result.center == (70, 55)


def test_wait_for_times_out_when_absent():
    frame = _make_frame(with_button=False)
    template = _pattern(40, 30)
    flow = Flow(screenshot=lambda: frame, click=lambda x, y: None, dry_run=True)

    with pytest.raises(FlowTimeout):
        flow.wait_for(template, timeout=0.3, interval=0.1)


def test_click_when_ready_dry_run_does_not_call_click():
    frame = _make_frame()
    template = frame[40:70, 50:90].copy()
    clicks = []
    flow = Flow(screenshot=lambda: frame, click=lambda x, y: clicks.append((x, y)), dry_run=True)

    flow.click_when_ready(template, timeout=2.0)

    assert clicks == []


def test_click_when_ready_real_click():
    frame = _make_frame()
    template = frame[40:70, 50:90].copy()
    clicks = []
    flow = Flow(screenshot=lambda: frame, click=lambda x, y: clicks.append((x, y)), dry_run=False)

    flow.click_when_ready(template, timeout=2.0)

    assert clicks == [(70, 55)]


def test_run_steps_wait_and_click():
    frame = _make_frame()
    template = frame[40:70, 50:90].copy()
    clicks = []
    flow = Flow(screenshot=lambda: frame, click=lambda x, y: clicks.append((x, y)), dry_run=False)
    logs = []

    run_steps(
        flow,
        [
            {"name": "等按钮", "action": "wait", "template": template, "timeout": 2},
            {"name": "点按钮", "action": "click", "template": template, "timeout": 2},
        ],
        log=logs.append,
    )

    assert clicks == [(70, 55)]
    assert logs == ["[OK] 等按钮", "[OK] 点按钮"]


def test_run_steps_skip_on_fail():
    frame = _make_frame(with_button=False)
    template = _pattern(40, 30)
    flow = Flow(screenshot=lambda: frame, click=lambda x, y: None, dry_run=True)
    logs = []

    run_steps(
        flow,
        [
            {"name": "找不到的按钮", "action": "wait", "template": template, "timeout": 0.3},
        ],
        on_fail="skip",
        log=logs.append,
    )

    assert any("FAIL" in line for line in logs)
    assert any("SKIP" in line for line in logs)
