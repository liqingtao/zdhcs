# -*- encoding=utf8 -*-
__author__ = "codex"

from airtest.core.api import *

auto_setup(__file__)

# 首页应出现"开始任务"按钮。
assert_exists(Template("btn_start.png", threshold=0.85), "首页应出现开始任务按钮")

# 点击"开始任务"按钮。
touch(Template("btn_start.png", threshold=0.85))

sleep(1)

# 点击后应出现"领取奖励"按钮。
assert_exists(Template("btn_reward.png", threshold=0.85), "点击后应出现领取奖励按钮")

log("冒烟用例通过", snapshot=True)

