# -*- coding: utf-8 -*-
"""跑商流程的配置：模板路径、城市识别关键词、买卖阈值、延时、重试等。

这是"真实落地"的集中开关。离线 demo 用它自带的假模板；接真实游戏时，先用
tools/capture_template.py 从你的游戏画面里截出按钮，保存到 assets/templates/ 下
同名文件，再把 CITY_KEYWORDS 换成你游戏里两个城市的名字（OCR 关键词）。
"""
from __future__ import annotations

from pathlib import Path

import config


def _t(name: str) -> str:
    return str(config.TEMPLATES_DIR / name)


# 四个按钮模板。接真实游戏时用 capture_template 采集到这些同名文件即可。
TEMPLATES = {
    "btn_buy": _t("btn_buy.png"),
    "btn_goto_sell": _t("btn_goto_sell.png"),
    "btn_sell": _t("btn_sell.png"),
    "btn_goto_buy": _t("btn_goto_buy.png"),
}

# 用 OCR 判断"当前在哪个城"。跑商界面标题/地标里必须能读到对应关键词。
# 离线假画面用"买入城/卖出城"；真实游戏请改成实际城市名（如 长安 / 洛阳）。
CITY_KEYWORDS = {
    "buy": "买入城",
    "sell": "卖出城",
}

# 价格判断阈值：买入价低于此值才买，收购价高于此值才卖。
BUY_MAX_PRICE = 9000
SELL_MIN_PRICE = 11000

# 识别点击的默认阈值与方法。
THRESHOLD = 0.85
METHOD = "TM_CCOEFF_NORMED"

# 一轮流程的节奏：每次动作间的随机延时范围（秒），以及等待元素出现的超时。
DELAY_RANGE = (0.5, 1.5)
WAIT_TIMEOUT = 10.0

# 兜底：最多跑几轮、未知状态最多重试几次。
MAX_ROUNDS = 10
UNKNOWN_STATE_RETRIES = 3
