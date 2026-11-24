# -*- coding: utf-8 -*-
"""刷经验流程的配置：模板、状态关键词、等待超时、重试等。

刷经验是"挂机刷怪"式的循环状态机：
    开始刷怪 -> 进入战斗(血条) -> 战斗结束(领取经验) -> 继续刷怪 -> 下一轮

和打图不同，刷经验没有"交任务"这一步，战斗结束后点"领取经验"再点"继续挑战"
直接进入下一场战斗。接真实游戏时用 tools/capture_template.py 采集同名模板，
并按需调整 STATE_KEYWORDS。
"""
from __future__ import annotations

import config


def _t(name: str) -> str:
    return str(config.TEMPLATES_DIR / name)


# 四个锚点模板：开始按钮 / 血条 / 领取经验 / 继续挑战，用 capture_template 采集。
TEMPLATES = {
    "btn_start_grind": _t("btn_start_grind.png"),      # 开始刷怪按钮
    "btn_enter_battle": _t("btn_enter_battle.png"),    # 进入战斗的锚点（血条/怪物）
    "btn_collect_xp": _t("btn_collect_xp.png"),        # 战斗结束后的领取经验按钮
    "btn_continue": _t("btn_continue.png"),            # 继续挑战/下一轮按钮
}

# 导航锚点：不在功能页面时点它触发游戏自动寻路（默认采集自任务追踪里的
# NPC 名，用 tools/capture_template.py 从你的当前任务里重新采集同名文件）。
NAV_TEMPLATE = _t("nav_quest_npc.png")

# OCR 状态关键词，用于日志提示"现在大概在哪个阶段"（辅助，不驱动流程）。
STATE_KEYWORDS = {
    "idle": "刷怪",
    "battle": "战斗",
    "reward": "经验",
}

# 识别点击阈值与方法。
THRESHOLD = 0.85
METHOD = "TM_CCOEFF_NORMED"

# 节奏：动作间随机延时范围，以及各阶段等待超时。
DELAY_RANGE = (0.5, 1.5)
WAIT_TIMEOUT = 10.0          # 普通元素等待
BATTLE_TIMEOUT = 120.0       # 刷经验一场战斗可能较长

# 兜底：最多跑几轮、未知状态最多重试几次。
MAX_ROUNDS = 10
UNKNOWN_STATE_RETRIES = 3
