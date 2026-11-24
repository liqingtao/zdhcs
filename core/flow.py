# -*- coding: utf-8 -*-
"""流程自动化原语：等待、点击、超时、重试、随机延时、步骤表执行器。

设计目标是把"截屏 -> 找图 -> 点击"的循环封装成可复用的几块，跑商/打图这类
状态机流程直接拼这些原语即可。为了既能接真实屏幕、又能离线跑假画面，这里把
"画面从哪来、点击打到哪"抽象成两个可注入的回调：

    flow = Flow(screenshot=screen.screenshot, click=lambda x, y: screen.click(x, y))

离线演示时换成假画面的 screenshot/click 即可，流程代码完全不变。
"""
from __future__ import annotations

import random
import time
from typing import Callable, List, Optional, Sequence

import numpy as np

from core import matcher


class FlowTimeout(RuntimeError):
    """等待元素出现的超时异常。"""


class Flow:
    def __init__(
        self,
        screenshot: Callable[[], np.ndarray],
        click: Callable[..., None],
        threshold: float = 0.85,
        method: str = "TM_CCOEFF_NORMED",
        dry_run: bool = True,
        delay_range: Sequence[float] = (0.5, 1.5),
    ) -> None:
        self.screenshot = screenshot
        self._click = click
        self.threshold = threshold
        self.method = method
        self.dry_run = dry_run
        self.delay_range = tuple(delay_range)

    # ------------------------------------------------------------------ 基础
    def pause(self) -> None:
        """模拟真人操作节奏的随机停顿，降低被当成脚本的概率。"""
        time.sleep(random.uniform(*self.delay_range))

    def find(
        self,
        template,
        threshold: Optional[float] = None,
    ) -> matcher.MatchResult:
        frame = self.screenshot()
        return matcher.find_template(
            frame,
            template,
            threshold=threshold if threshold is not None else self.threshold,
            method=self.method,
        )

    def wait_for(
        self,
        template,
        timeout: float = 10.0,
        interval: float = 0.5,
        threshold: Optional[float] = None,
    ) -> matcher.MatchResult:
        """循环截屏，直到模板出现；超时抛 FlowTimeout。"""
        deadline = time.time() + timeout
        last: Optional[matcher.MatchResult] = None
        while time.time() < deadline:
            last = self.find(template, threshold=threshold)
            if last.found:
                return last
            time.sleep(interval)
        best = f"{last.confidence:.3f}" if last is not None else "n/a"
        raise FlowTimeout(f"等待超时: {template}（best={best}，timeout={timeout}s）")

    def click_when_ready(
        self,
        template,
        timeout: float = 10.0,
        interval: float = 0.5,
        threshold: Optional[float] = None,
    ) -> matcher.MatchResult:
        """等模板出现后点击其中心；dry_run 时只打印坐标。"""
        result = self.wait_for(template, timeout=timeout, interval=interval, threshold=threshold)
        if self.dry_run:
            print(f"[dry-run] 模拟点击 {result.center}")
        else:
            self._click(*result.center)
        return result

    # ------------------------------------------------------------------ OCR
    def read_text(self, engine=None, keyword: Optional[str] = None):
        """读当前画面文字；keyword 非空时只返回包含它的行。"""
        from core.ocr import create_engine

        engine = engine or create_engine()
        frame = self.screenshot()
        results = engine.read_text(frame)
        if keyword is not None:
            return [r for r in results if keyword in r.text]
        return results


def run_steps(
    flow: Flow,
    steps: Sequence[dict],
    on_fail: str = "abort",
    log: Callable[[str], None] = print,
) -> List[dict]:
    """按步骤表执行流程，支持每步重试；on_fail 取 abort / skip。

    每步是一个 dict，常用字段：
        name     步骤名（日志用）
        action   动作：wait / click / ocr / call
        template 图片路径（wait / click 用）
        keyword  OCR 关键词（ocr 用）
        timeout  等待超时秒数（wait / click 用）
        retries  失败后重试次数（默认 0）
        fn       自定义无参回调（action=call 用）

    ocr 步骤会把命中结果写回 step["result"]，方便后续步骤读取。
    """
    results: List[dict] = []
    for step in steps:
        name = step.get("name", "未命名步骤")
        action = step.get("action", "click")
        retries = int(step.get("retries", 0))
        template = step.get("template")
        threshold = step.get("threshold")

        for attempt in range(retries + 1):
            try:
                if action == "wait":
                    flow.wait_for(template, timeout=step.get("timeout", 10), threshold=threshold)
                elif action == "click":
                    flow.click_when_ready(template, timeout=step.get("timeout", 10), threshold=threshold)
                elif action == "ocr":
                    hits = flow.read_text(keyword=step.get("keyword"))
                    if step.get("expect_found", True) and not hits:
                        raise RuntimeError(f"OCR 未找到关键词 {step.get('keyword')!r}")
                    step["result"] = hits
                elif action == "call":
                    fn = step.get("fn")
                    if fn is None:
                        raise ValueError("action=call 需要提供 fn")
                    fn()
                else:
                    raise ValueError(f"未知 action: {action!r}")
                log(f"[OK] {name}")
                break
            except Exception as exc:  # noqa: BLE001
                log(f"[FAIL] {name}：{exc}（第 {attempt + 1}/{retries + 1} 次）")
                if attempt >= retries:
                    if on_fail == "skip":
                        log(f"[SKIP] {name}")
                    else:
                        raise
                else:
                    flow.pause()
        results.append(step)
    return results
