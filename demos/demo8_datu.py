# -*- coding: utf-8 -*-
"""第 8 步：打图自动化示例（线性状态机 + 锚点驱动）。

离线演示"领取任务 -> 自动寻路 -> 进入战斗 -> 战斗结束 -> 拾取 -> 交任务"的
状态流转。用 FakeScreen 模拟屏幕/点击，流程代码与真实屏幕共用 core.flow 原语。

运行：
    python -m demos.demo8_datu --rounds 2
"""
from __future__ import annotations

import argparse

import config
import datu_config as cfg
from core.flow import Flow
from demos.make_datu_scene import _render, _to_bgr


class FakeScreen:
    """模拟打图客户端：截图返回当前状态画面，点击推进状态。"""

    def __init__(self) -> None:
        self.state = "task"
        self.round = 1
        self._battle_ticks = 0

    def screenshot(self):
        # 战斗中，经过几次截图后自动"战斗结束"，模拟真实战斗耗时。
        if self.state == "battle":
            self._battle_ticks += 1
            if self._battle_ticks >= 3:
                self.state = "reward"
                self._battle_ticks = 0
        return _to_bgr(_render(self.state, self.round))

    def click(self, x: int, y: int) -> None:
        # 按钮坐标和 make_datu_scene 保持一致。
        if self.state == "task" and 250 <= x <= 550 and 250 <= y <= 330:
            self.state = "route"
        elif self.state == "route" and 250 <= x <= 550 and 250 <= y <= 330:
            self.state = "battle"
        elif self.state == "reward" and 200 <= x <= 360 and 250 <= y <= 330:
            pass  # 拾取后仍停留奖励页，等点交任务
        elif self.state == "reward" and 440 <= x <= 600 and 250 <= y <= 330:
            self.state = "task"
            self.round += 1


def run_datu_demo(rounds: int = 2) -> None:
    fake = FakeScreen()
    fl = Flow(
        screenshot=fake.screenshot,
        click=fake.click,
        dry_run=False,
        delay_range=(0.0, 0.0),
        threshold=cfg.THRESHOLD,
        method=cfg.METHOD,
    )

    completed = 0
    while completed < rounds:
        print(f"\n===== 第 {completed + 1} 轮 =====")
        fl.click_when_ready(cfg.TEMPLATES["btn_take_task"], timeout=5)
        print("[领取任务] 已点击")

        fl.click_when_ready(cfg.TEMPLATES["btn_auto_route"], timeout=5)
        print("[自动寻路] 已点击")

        fl.wait_for(cfg.TEMPLATES["btn_enter_battle"], timeout=10)
        print("[进入战斗] 血条锚点出现")

        fl.wait_for(cfg.TEMPLATES["btn_pickup"], timeout=10)
        print("[战斗结束] 拾取按钮出现")

        fl.click_when_ready(cfg.TEMPLATES["btn_pickup"], timeout=5)
        print("[拾取] 已点击")

        fl.click_when_ready(cfg.TEMPLATES["btn_turnin"], timeout=5)
        print("[交任务] 已点击")

        completed += 1
        print(f"[完成] 第 {completed} 轮结束")

    print(f"\n===== 结束，完成 {completed} 轮 =====")


def main() -> None:
    from demos.make_datu_scene import make_templates

    make_templates()
    parser = argparse.ArgumentParser(description="打图自动化示例")
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    run_datu_demo(args.rounds)


if __name__ == "__main__":
    main()
