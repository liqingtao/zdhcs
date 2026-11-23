# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（onedir，控制台程序）。

在项目根目录执行：pyinstaller --clean --noconfirm zdhcs.spec
产物：dist/zdhcs/zdhcs.exe

OCR/Airtest 属于重依赖（onnxruntime / paddle / 模型文件），默认不打进 exe；
exe 里的 ocr 子命令在缺引擎时会提示从源码安装。
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

for _pkg in ("pyautogui", "pyscreeze", "PIL"):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception:
        pass

a = Analysis(
    ["zdhcs.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "airtest",
        "pocoui",
        "paddle",
        "paddleocr",
        "rapidocr_onnxruntime",
        "onnxruntime",
        "tkinter",
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
    console=True,
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

