# -*- coding: utf-8 -*-
"""第 9 步：刷经验自动化示例（挂机刷怪循环 + 锚点驱动）。

离线演示"开始刷怪 -> 进入战斗 -> 战斗结束 -> 领取经验 -> 继续挑战"的循环。
用 FakeScreen 模拟屏幕/点击，流程代码与真实屏幕共用 core.flow 原语。

运行：
    python -m demos.demo9_shuajingyan --rounds 2
"""
from __future__ import annotations

import argparse

import config
import shuajingyan_config as cfg
from core.flow import Flow
from demos.make_shuajingyan_scene import _render, _to_bgr


class FakeScreen:
    """模拟刷经验客户端：截图返回当前状态画面，点击推进状态。"""

    def __init__(self) -> None:
        self.state = "idle"
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
        # 按钮坐标和 make_shuajingyan_scene 保持一致。
        if self.state == "idle" and 250 <= x <= 550 and 250 <= y <= 330:
            self.state = "battle"
        elif self.state == "reward" and 200 <= x <= 360 and 250 <= y <= 330:
            pass  # 领取经验后仍停留奖励页，等点继续挑战
        elif self.state == "reward" and 440 <= x <= 600 and 250 <= y <= 330:
            self.state = "battle"
            self.round += 1


def run_shuajingyan_demo(rounds: int = 2) -> None:
    fake = FakeScreen()
    fl = Flow(
        screenshot=fake.screenshot,
        click=fake.click,
        dry_run=False,
        delay_range=(0.0, 0.0),
        threshold=cfg.THRESHOLD,
        method=cfg.METHOD,
    )

    # 开场：点"开始刷怪"进入第一次战斗。
    fl.click_when_ready(cfg.TEMPLATES["btn_start_grind"], timeout=5)
    print("[开始] 已开始刷怪")

    completed = 0
    while completed < rounds:
        print(f"\n===== 第 {completed + 1} 轮 =====")

        fl.wait_for(cfg.TEMPLATES["btn_enter_battle"], timeout=10)
        print("[进入战斗] 血条锚点出现")

        fl.wait_for(cfg.TEMPLATES["btn_collect_xp"], timeout=10)
        print("[战斗结束] 领取经验按钮出现")

        fl.click_when_ready(cfg.TEMPLATES["btn_collect_xp"], timeout=5)
        print("[领取经验] 已点击")

        fl.click_when_ready(cfg.TEMPLATES["btn_continue"], timeout=5)
        print("[继续挑战] 已点击")

        completed += 1
        print(f"[完成] 第 {completed} 轮结束")

    print(f"\n===== 结束，完成 {completed} 轮 =====")


def main() -> None:
    from demos.make_shuajingyan_scene import make_templates

    make_templates()
    parser = argparse.ArgumentParser(description="刷经验自动化示例")
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    run_shuajingyan_demo(args.rounds)


if __name__ == "__main__":
    main()
