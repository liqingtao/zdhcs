# -*- coding: utf-8 -*-
"""新号剧情流程的配置：模板、状态关键词、等待超时、重试等。

新号剧情是"跟着任务追踪走"的线性流程：点任务追踪 NPC 名自动寻路 ->
到达后对话 -> 依次点对话选项（继续 / 确认 / 关闭）-> 如遇战斗自动处理
-> 重复直到剧情完成。

接真实游戏时用 tools/capture_template.py 采集同名模板，并按需调整
STATE_KEYWORDS。导航锚点 nav_quest_npc.png 与打图/刷经验共用。
"""
from __future__ import annotations

import config


def _t(name: str) -> str:
    return str(config.TEMPLATES_DIR / name)


# 剧情流程锚点模板：用 capture_template 采集到同名文件。
TEMPLATES = {
    "nav_quest_npc": _t("nav_quest_npc.png"),           # 任务追踪 NPC 名（点击寻路）
    "btn_dialog_continue": _t("btn_dialog_continue.png"),  # 对话"继续/下一句"
    "btn_dialog_confirm": _t("btn_dialog_confirm.png"),    # 对话"确认/好的"
    "btn_dialog_close": _t("btn_dialog_close.png"),        # 对话结束后"关闭/完成"
    "btn_enter_battle": _t("btn_enter_battle.png"),        # 进入战斗（血条/怪物）
    "btn_pickup": _t("btn_pickup.png"),                    # 战斗结束拾取
}

# 导航锚点（与打图/刷经验共用同一张图）。
NAV_TEMPLATE = _t("nav_quest_npc.png")

# OCR 状态关键词，用于日志提示。
STATE_KEYWORDS = {
    "quest": "剧情",
    "dialog": "对话",
    "battle": "战斗",
    "reward": "奖励",
}

# 识别点击阈值与方法。
THRESHOLD = 0.85
METHOD = "TM_CCOEFF_NORMED"

# 节奏。
DELAY_RANGE = (0.8, 2.0)
WAIT_TIMEOUT = 8.0           # 对话按钮等待
BATTLE_TIMEOUT = 120.0       # 剧情战斗可能较长
ROUTE_TIMEOUT = 60.0         # 自动寻路等待（到达后对话会出现）

# 对话按钮点击顺序：按优先级依次尝试，找到哪个点哪个。
DIALOG_CLICK_ORDER = [
    "btn_dialog_continue",
    "btn_dialog_confirm",
    "btn_dialog_close",
]

# 兜底。
MAX_STEPS = 20               # 最多跑多少个"点击NPC→对话"循环
UNKNOWN_STATE_RETRIES = 3
