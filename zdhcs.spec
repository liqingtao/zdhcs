# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（onedir，窗口程序）。

在项目根目录执行：pyinstaller --clean --noconfirm zdhcs.spec
产物：dist/zdhcs/zdhcs.exe（双击打开图形界面）

OCR 与 Airtest 两个重依赖默认一并打进包里：
- OCR：rapidocr_onnxruntime + onnxruntime（跨平台、模型随包分发，无需联网下载）。
- Airtest：airtest + pocoui/poco，把 touch(Template(...))/assert_exists 带进 exe。

PaddleOCR / paddlepaddle 体积过大且 PyInstaller 打包脆弱，保持不打入，OCR 能力由 RapidOCR 提供。
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

for _pkg in (
    "pyautogui",
    "pyscreeze",
    "PIL",
    "airtest",
    "poco",
    "rapidocr_onnxruntime",
    "onnxruntime",
    "pyclipper",
    "shapely",
):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception:
        pass

# 把模板和资源文件打进包里（打包后在 exe 同级 assets/ 下）。
datas += [
    ("assets", "assets"),
]

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "paddle",
        "paddleocr",
        "paddlepaddle",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="zdhcs",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="zdhcs",
)

