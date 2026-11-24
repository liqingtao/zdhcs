"""屏幕截图与鼠标点击。

PyAutoGUI 只负责"输入输出"（截图、移动鼠标、点击），真正的图像识别交给
core.matcher 做。这样职责清晰：I/O 一个模块，视觉一个模块。

macOS 上要让截图/点击生效，需要先在"系统设置 -> 隐私与安全性"里给终端
（或你的 Python/IDE）开启"辅助功能"和"屏幕录制"权限。
"""
from pathlib import Path
from typing import Optional, Tuple, Union

import cv2
import numpy as np


def _to_bgr(pil_image) -> np.ndarray:
    """PIL 默认是 RGB，OpenCV 用的是 BGR，这里做一次转换。"""
    rgb = np.asarray(pil_image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _save(bgr: np.ndarray, path: Union[str, Path]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), bgr)
    return path


def screenshot(
    path: Union[str, Path, None] = None,
    region: Optional[Tuple[int, int, int, int]] = None,
    backend: str = "pyautogui",
) -> np.ndarray:
    """截取全屏或指定区域，返回 BGR ndarray，可选直接保存为 PNG。

    region 使用 (left, top, width, height) 的 PyAutoGUI 约定。

    Windows 上 PyAutoGUI 的截图在部分环境（锁屏 / 沙箱桌面 / 特定驱动）会直接
    抛错，这里做成降级链：pyautogui -> PIL ImageGrab -> mss，谁可用用谁。
    """
    order = [backend] + [b for b in ("pyautogui", "pil", "mss") if b != backend]
    last_error: Optional[Exception] = None
    for name in order:
        try:
            bgr = _screenshot_backend(name, region)
            if path is not None:
                _save(bgr, path)
            return bgr
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"所有截图后端都失败了: {last_error}") from last_error


def _screenshot_backend(
    backend: str,
    region: Optional[Tuple[int, int, int, int]],
) -> np.ndarray:
    if backend == "pyautogui":
        import pyautogui

        img = pyautogui.screenshot(region=region)
        return _to_bgr(img)

    if backend == "pil":
        from PIL import ImageGrab

        # PIL 的 bbox 是 (left, top, right, bottom)。
        bbox = None
        if region is not None:
            left, top, width, height = region
            bbox = (left, top, left + width, top + height)
        img = ImageGrab.grab(bbox=bbox)
        return _to_bgr(img)

    if backend == "mss":
        import mss

        with mss.mss() as sct:
            if region is None:
                monitor = sct.monitors[1]
            else:
                left, top, width, height = region
                monitor = {"left": left, "top": top, "width": width, "height": height}
            shot = sct.grab(monitor)
        return np.asarray(shot)[:, :, :3].copy()  # BGRA -> BGR

    raise ValueError(f"未知截图后端: {backend!r}，可选 pyautogui / pil / mss")

    bgr = _to_bgr(img)
    if path is not None:
        _save(bgr, path)
    return bgr


def click(
    x: int,
    y: int,
    dry_run: bool = True,
    clicks: int = 1,
    interval: float = 0.0,
    button: str = "left",
) -> None:
    """点击坐标。默认 dry_run=True，只打印不真点，避免误触。"""
    if dry_run:
        print(f"[dry-run] 模拟点击 ({x}, {y})，button={button}，clicks={clicks}")
        return

    import pyautogui

    pyautogui.click(x, y, clicks=clicks, interval=interval, button=button)
    print(f"[click] 已点击 ({x}, {y})")

