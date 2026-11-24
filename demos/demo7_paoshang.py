# -*- coding: utf-8 -*-
"""第 7 步：跑商自动化示例（状态机 + OCR 决策 + 识别点击）。

离线演示一个"跑商"闭环：在买入城读价格，低价买入；货满后去卖出城，读收购价，
高价卖出；卖完回买入城，如此循环。用 FakeScreen 模拟屏幕和点击，流程代码与
真实屏幕共用 core.flow 原语，拿到真实模板/坐标后替换即可。

运行：
    python -m demos.demo7_paoshang --rounds 2
"""
from __future__ import annotations

import argparse
import re
import random

import config
from core import flow
from core.flow import Flow
from demos.make_paoshang_scene import _render, _to_bgr


class FakeScreen:
    """模拟一个跑商客户端：截图返回当前画面，点击会改变城市/货物/资金。"""

    def __init__(self) -> None:
        self.city = "buy"
        self.goods = 0
        self.money = 100000
        self.buy_price = 8500
        self.sell_price = 12000

    def screenshot(self):
        price = self.buy_price if self.city == "buy" else self.sell_price
        return _to_bgr(_render(self.city, price, self.goods, self.money))

    def click(self, x: int, y: int) -> None:
        # 按钮坐标和 make_paoshang_scene 里保持一致。
        left_btn = 200 <= x <= 360 and 260 <= y <= 330
        right_btn = 440 <= x <= 620 and 260 <= y <= 330

        if self.city == "buy" and left_btn:
            if self.money >= self.buy_price:
                self.goods += 20
                self.money -= self.buy_price * 20
        elif self.city == "buy" and right_btn and self.goods > 0:
            self.city = "sell"
        elif self.city == "sell" and left_btn and self.goods > 0:
            self.money += self.sell_price * self.goods
            self.goods = 0
        elif self.city == "sell" and right_btn:
            self.city = "buy"
            self._next_round_prices()

    def _next_round_prices(self) -> None:
        # 下一轮价格随机波动，模拟真实行情，让 OCR 决策有变化。
        self.buy_price = random.randint(7800, 9800)
        self.sell_price = random.randint(10500, 13000)


def _price_from_ocr(results) -> int:
    """从 OCR 结果里抠出价格数字。"""
    for r in results:
        m = re.search(r"(\d{3,6})", r.text)
        if m:
            return int(m.group(1))
    return 0


def run_paoshang(rounds: int = 2) -> None:
    fake = FakeScreen()
    fl = Flow(
        screenshot=fake.screenshot,
        click=fake.click,
        dry_run=False,  # FakeScreen 的点击是模拟的，可以放心真点
        delay_range=(0.0, 0.0),  # 演示时不停顿，真实脚本改成 (0.5, 1.5)
    )

    from core.ocr import create_engine

    engine = create_engine()

    for rnd in range(1, rounds + 1):
        print(f"\n===== 第 {rnd} 轮 =====")

        # 1. 在买入城：读价，低价就买入
        flow.run_steps(
            fl,
            [
                {"name": "等买入按钮", "action": "wait", "template": config.TEMPLATES_DIR / "btn_buy.png", "timeout": 5},
            ],
        )

        # 读买入价，低价就买。
        buy_results = fl.read_text(keyword="买入价", engine=engine)
        buy_price = _price_from_ocr(buy_results)
        print(f"[买入城] 读到买入价 {buy_price}")
        if buy_price <= 9000:
            fl.click_when_ready(config.TEMPLATES_DIR / "btn_buy.png", timeout=5)
            print("[买入城] 低价，已买入 20 件")
        else:
            print("[买入城] 价格偏高，跳过买入")

        # 2. 去卖出城（货满才去）
        if fake.goods > 0:
            fl.click_when_ready(config.TEMPLATES_DIR / "btn_goto_sell.png", timeout=5)
            print("[买入城] 前往卖出城")

            # 3. 在卖出城：读收购价，高价就卖
            fl.wait_for(config.TEMPLATES_DIR / "btn_sell.png", timeout=5)
            sell_results = fl.read_text(keyword="收购价", engine=engine)
            sell_price = _price_from_ocr(sell_results)
            print(f"[卖出城] 读到收购价 {sell_price}")
            if sell_price >= 11000:
                fl.click_when_ready(config.TEMPLATES_DIR / "btn_sell.png", timeout=5)
                print(f"[卖出城] 高价，已卖出，赚 {(sell_price - buy_price) * 20}")
            else:
                print("[卖出城] 价格偏低，继续持有")

            # 4. 返回买入城，进入下一轮
            fl.click_when_ready(config.TEMPLATES_DIR / "btn_goto_buy.png", timeout=5)
            print("[卖出城] 返回买入城")

    print(f"\n===== 结束 =====")
    print(f"最终资金 {fake.money}，货物 {fake.goods}")


def main() -> None:
    from demos.make_paoshang_scene import make_templates

    make_templates()
    parser = argparse.ArgumentParser(description="跑商自动化示例")
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    run_paoshang(args.rounds)


if __name__ == "__main__":
    main()
