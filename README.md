# 梦幻西游自动化测试练习项目

一个从零到一的桌面/游戏自动化测试练手项目，把五块技术串成一条可运行的学习路径：

1. **PyAutoGUI** —— 负责"手"：截图、移动鼠标、点击。
2. **OpenCV** —— 负责"眼睛"：模板匹配 + 阈值，判断按钮有没有出现、在哪。
3. **Airtest** —— 用测试框架把前面能力组织成用例，产出断言和 HTML 报告。
4. **PaddleOCR / RapidOCR** —— 在需要读文字（倒计时、任务状态）时接入 OCR。

项目不绑定具体游戏，内置了一张"假游戏画面"用于离线演示，跑通后再替换成真实截图和模板即可。

## 目录结构

```text
zdhcs/
├── config.py                    # 路径、默认阈值等公共配置
├── core/
│   ├── matcher.py               # OpenCV 模板匹配 + 阈值（核心）
│   ├── screen.py                # PyAutoGUI 截图/点击
│   └── ocr.py                   # PaddleOCR 封装
├── demos/
│   ├── make_fake_screen.py      # 生成假游戏画面 + 按钮模板
│   ├── demo1_pyautogui.py       # 截图 -> 找图 -> 点击
│   ├── demo2_opencv.py          # 模板匹配 + 阈值 + 热力图
│   ├── demo3_airtest.py         # touch(Template) / assert_exists 入口
│   └── demo4_ocr.py             # PaddleOCR 读文字
├── airtest_cases/
│   ├── run_airtest.py           # 跑 .air 用例并生成报告
│   └── smoke.air/smoke.py       # 可执行的 Airtest 用例
├── assets/
│   ├── templates/               # 按钮模板图
│   └── screenshots/             # 截图/热力图输出
└── tests/test_matcher.py        # 纯 OpenCV 单元测试（离线可跑）
```

## 快速开始（先跑通离线核心）

```bash
cd /Users/shaoke/Documents/Claude/mhxy/zdhcs

# 建独立环境并装核心依赖（numpy / opencv / pillow / pytest）
make install

# 生成假游戏画面 + 两个按钮模板
make fake

# 跑模板匹配 demo，看命中结果、热力图、阈值扫描
make demo2

# 跑单元测试
make test
```

不想用 `make` 也可以直接：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m demos.make_fake_screen
.venv/bin/python -m demos.demo2_opencv
.venv/bin/python -m pytest -q
```

## 五个技术点怎么学

### 1. PyAutoGUI：截图 -> 找图 -> 点击

文件：[demos/demo1_pyautogui.py](demos/demo1_pyautogui.py)、[core/screen.py](core/screen.py)

```bash
# 离线演示：用本地假画面代替真实截屏，点击默认 dry-run（只打印坐标）
.venv/bin/python -m demos.demo1_pyautogui --screen assets/screenshots/fake_screen.png

# 真实截屏并真正点击（需要先开权限）
.venv/bin/python -m demos.demo1_pyautogui --no-dry-run
```

PyAutoGUI 只做 I/O：`screenshot()` 抓屏、`click(x, y)` 点击；"图在哪"交给 OpenCV。
macOS 上第一次跑要在「系统设置 -> 隐私与安全性 -> 辅助功能 / 屏幕录制」里勾选终端或 Python。

### 2. OpenCV：模板匹配和阈值

文件：[core/matcher.py](core/matcher.py)、[demos/demo2_opencv.py](demos/demo2_opencv.py)、[tests/test_matcher.py](tests/test_matcher.py)

这是整条链路的关键。判断"画面上有没有某个按钮"，本质是：

```python
heat = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(heat)
found = max_val >= threshold
```

- `matchTemplate` 让模板在画面上滑动，算出一个"相似度热力图"。
- `minMaxLoc` 找到最像的位置和分数。
- `threshold` 决定"多少分算找到"。默认用 `TM_CCOEFF_NORMED`，取值约在 `[-1, 1]`，`1` 表示完全一致，`0.85` 是比较稳的起步值。

`demo2` 会额外保存 `assets/screenshots/heatmap.png`（热力图）和 `matched.png`（匹配框标注），并打印阈值从 0.60 到 1.00 的命中变化，帮你建立对"阈值"的手感。

注意：`TM_SQDIFF_NORMED` 这类方法是**越小越好**（0 表示完美），本项目的 `find_template` 已经统一转成"越大越像"，避免记错方向。

### 3. Airtest：组织用例 + 断言 + 报告

文件：[airtest_cases/smoke.air/smoke.py](airtest_cases/smoke.air/smoke.py)、[airtest_cases/run_airtest.py](airtest_cases/run_airtest.py)、[demos/demo3_airtest.py](demos/demo3_airtest.py)

```python
assert_exists(Template("btn_start.png", threshold=0.85), "首页应出现开始任务按钮")
touch(Template("btn_start.png", threshold=0.85))
sleep(1)
assert_exists(Template("btn_reward.png", threshold=0.85), "点击后应出现领取奖励按钮")
```

对应到低层原语：`touch(Template(...))` ≈ `find_template()` + `click(center)`；`assert_exists` ≈ 判断 `find_template().found` 为真。

运行（需要先装 Airtest 并连接设备）：

```bash
.venv/bin/python -m pip install -r requirements-airtest.txt
.venv/bin/python -m airtest_cases.run_airtest --device Android:///
```

报告默认输出到 `log/report.html`。Airtest 依赖较重，且自带 `opencv-contrib-python`，建议单独放一个 venv，避免和核心环境的 `opencv-python-headless` 冲突。

### 4. PaddleOCR / RapidOCR：读倒计时/状态文字

文件：[core/ocr.py](core/ocr.py)、[demos/demo4_ocr.py](demos/demo4_ocr.py)

```bash
# 二选一：PaddleOCR（Linux/Windows 推荐），或 rapidocr（macOS 更省事）
.venv/bin/python -m pip install -r requirements-ocr.txt
.venv/bin/python -m pip install -r requirements-ocr-rapid.txt
.venv/bin/python -m demos.demo4_ocr --image assets/screenshots/fake_screen.png
.venv/bin/python -m demos.demo4_ocr --image assets/screenshots/fake_screen.png --keyword 00:30
```

`read_text()` 返回 `TextResult(text, confidence, box)` 列表；`find_text()` 按关键词过滤。
`core/ocr.py` 里的 `create_engine()` 会优先用 PaddleOCR，没装就回退到 rapidocr，接口一致。
PaddleOCR 首次运行要下载模型（几百 MB），且 PaddlePaddle 对 macOS 支持有限；macOS 上更推荐用
`requirements-ocr-rapid.txt` 里的 rapidocr（onnxruntime），轻量且跨平台。

## 验证边界

- 已在本机离线验证：`core/matcher.py` 的模板匹配、阈值判断、`find_all`、SQDIFF 方法、彩色匹配，通过 `pytest` 单测。
- 已离线验证：`make fake` 生成假画面，`demo2` 跑通并产出热力图。
- **未在本机验证**：PyAutoGUI 的真实截屏/点击（需要 macOS 权限和真实屏幕）、Airtest 的 `touch/assert_exists`（需要设备和依赖）、PaddleOCR 的真实识别（依赖体积大，未安装）。这些代码已按官方 API 编写，但请按上面各自章节安装依赖后实测。

## 打包 Windows 安装包

项目提供了一个统一入口 [zdhcs.py](zdhcs.py)，把常用能力收成子命令：

```bash
python zdhcs.py selftest                       # 自检 OpenCV 模板匹配
python zdhcs.py generate                       # 生成假画面/模板
python zdhcs.py find --screen X --template Y   # 找图
python zdhcs.py click --screen X --template Y  # 找图 + 点击（默认 dry-run）
python zdhcs.py ocr --image X --keyword 倒计时  # 读文字
python zdhcs.py airtest --screen X --template Y # Airtest Template.match_in 自检
```

打包成 Windows 可执行文件用 PyInstaller（配置见 [zdhcs.spec](zdhcs.spec)）。注意：**PyInstaller 不支持跨平台编译**，Windows 的 exe 必须在 Windows 上构建，两种方式：

1. 有 Windows 机器：拷贝整个项目过去，双击 [build/windows/build_windows.bat](build/windows/build_windows.bat)，产出 `dist\zdhcs\zdhcs.exe`；装了 Inno Setup 再跑 [build/windows/build_installer.bat](build/windows/build_installer.bat) 可得到 `Setup.exe` 安装包。
2. 没有 Windows 机器：把仓库推到 GitHub，触发 [.github/workflows/build-windows.yml](.github/workflows/build-windows.yml)，云端 windows-latest 会自动产出便携 zip 和 `Setup.exe`，在 Actions 的 Artifacts 里下载即可。

OCR 与 Airtest 两个重依赖会一并打进 exe：
- OCR 用 `rapidocr_onnxruntime` + `onnxruntime`，模型随包分发，`ocr` 子命令开箱即用。
- Airtest 用 `airtest` + `pocoui`，`airtest` 子命令可离线自检 `Template.match_in`。
- PaddleOCR / paddlepaddle 体积过大且打包脆弱，保持不打入，OCR 能力由 RapidOCR 提供。

Windows 包现在是**图形界面**：双击 `zdhcs.exe` 直接打开窗口（[gui.py](gui.py)），
界面提供「生成假画面 / 打开画面图 / 打开模板图 / 找图 / 找图+点击 / OCR 读文字 /
Airtest 自检」按钮，阈值和方法可调，结果会显示在预览区和日志区。命令行入口
[zdhcs.py](zdhcs.py) 保留，仍可 `python zdhcs.py <子命令>` 使用。

