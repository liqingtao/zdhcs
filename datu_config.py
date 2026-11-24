# -*- coding: utf-8 -*-
"""打图流程的配置：模板、状态关键词、等待超时、重试等。

打图和跑商不同，它是线性状态机：接任务 -> 自动寻路 -> 进入战斗 -> 战斗结束
(拾取) -> 交任务 -> 下一轮。驱动主要靠"下一个锚点模板出现"，OCR 关键词作为
状态日志辅助。接真实游戏时用 tools/capture_template.py 采集同名模板，并按需
调整 STATE_KEYWORDS。
"""
from __future__ import annotations

import config


def _t(name: str) -> str:
    return str(config.TEMPLATES_DIR / name)


# 五个锚点模板：按钮 / 血条 / 拾取图标等，用 capture_template 采集到同名文件。
TEMPLATES = {
    "btn_take_task": _t("btn_take_task.png"),      # 接任务按钮
    "btn_auto_route": _t("btn_auto_route.png"),    # 自动寻路按钮
    "btn_enter_battle": _t("btn_enter_battle.png"),  # 进入战斗的锚点（血条/怪物）
    "btn_pickup": _t("btn_pickup.png"),            # 战斗结束后的拾取按钮/图标
    "btn_turnin": _t("btn_turnin.png"),            # 交任务按钮
}

# OCR 状态关键词，用于日志里提示"现在大概在哪个阶段"（辅助，不驱动流程）。
STATE_KEYWORDS = {
    "task": "任务",
    "route": "寻路",
    "battle": "战斗",
    "reward": "奖励",
}

# 识别点击阈值与方法。
THRESHOLD = 0.85
METHOD = "TM_CCOEFF_NORMED"

# 节奏：动作间随机延时范围，以及各阶段等待超时。
DELAY_RANGE = (0.5, 1.5)
WAIT_TIMEOUT = 10.0          # 普通元素等待
BATTLE_TIMEOUT = 90.0        # 战斗从开始到结束可能很长

# 兜底：最多跑几轮、未知状态最多重试几次。
MAX_ROUNDS = 10
UNKNOWN_STATE_RETRIES = 3
