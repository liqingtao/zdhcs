# -*- coding: utf-8 -*-
"""托管窗口：绑定指定游戏窗口，后台截屏 + 前台/后台点击。

"托管"要解决的三个问题：
1. 区分窗口 —— 按 hwnd 绑定，截图和点击都只作用于这个窗口，多开互不影响。
2. 窗口在后台 —— 截图用 PrintWindow（DWM 直接渲染，不抢焦点）；点击两种模式：
       前台模式：窗口最小化先还原，再把真实点击发到窗口在屏幕上的位置；
       后台模式：PostMessage 直接把鼠标消息发给窗口，完全不抢焦点。
3. 不在功能页面 —— 配合 flow.ensure_on_page，点导航锚点自动寻路。
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes as wt
from typing import List, Optional, Tuple

import numpy as np

from core import screen

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_gdi32 = ctypes.windll.gdi32

PW_RENDERFULLCONTENT = 0x00000002
SW_RESTORE = 9
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x80
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


def _window_title(hwnd: int) -> str:
    n = _user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    _user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def list_windows(keyword: Optional[str] = None) -> List[Tuple[int, str]]:
    """列出所有可见、有标题的顶层窗口，可选按标题关键字过滤。"""
    results: List[Tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def _cb(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True
        if _user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        title = _window_title(hwnd)
        if not title:
            return True
        if keyword and keyword not in title:
            return True
        results.append((int(hwnd), title))
        return True

    _user32.EnumWindows(_cb, 0)
    return results


def find_window(keyword: str) -> Optional[int]:
    """按标题关键字找第一个窗口句柄，找不到返回 None。"""
    for hwnd, _title in list_windows(keyword):
        return hwnd
    return None


class WindowTarget:
    """一个被托管的游戏窗口。"""

    def __init__(self, hwnd: int) -> None:
        if not _user32.IsWindow(int(hwnd)):
            raise ValueError(f"无效的窗口句柄: {hwnd}")
        self.hwnd = int(hwnd)
        self.title = _window_title(self.hwnd)

    # ------------------------------------------------------------ 基本信息
    def _client_size(self) -> Tuple[int, int]:
        rect = wt.RECT()
        _user32.GetClientRect(self.hwnd, ctypes.byref(rect))
        return rect.right, rect.bottom

    def client_to_screen(self, x: int, y: int) -> Tuple[int, int]:
        pt = wt.POINT(int(x), int(y))
        _user32.ClientToScreen(self.hwnd, ctypes.byref(pt))
        return pt.x, pt.y

    def is_foreground(self) -> bool:
        return _user32.GetForegroundWindow() == self.hwnd

    def is_minimized(self) -> bool:
        return bool(_user32.IsIconic(self.hwnd))

    def restore(self) -> None:
        if self.is_minimized():
            _user32.ShowWindow(self.hwnd, SW_RESTORE)
            time.sleep(0.25)

    def activate(self) -> None:
        self.restore()
        if not self.is_foreground():
            _user32.SetForegroundWindow(self.hwnd)
            time.sleep(0.15)

    # ------------------------------------------------------------ 截屏
    def screenshot(self) -> np.ndarray:
        """截取窗口客户区，返回 BGR ndarray。

        优先 PrintWindow（后台也能截、不抢焦点）；拿到黑帧（部分独占渲染的
        游戏或最小化窗口）时退回：还原窗口 -> 按窗口区域抓真实屏幕。
        """
        frame = self._print_window_frame()
        if frame is not None and frame.max() > 0:
            return frame
        self.restore()
        x, y = self.client_to_screen(0, 0)
        w, h = self._client_size()
        return screen.screenshot(region=(x, y, w, h))

    def _print_window_frame(self) -> Optional[np.ndarray]:
        w, h = self._client_size()
        if w <= 0 or h <= 0:
            return None
        hdc_window = _user32.GetWindowDC(self.hwnd)
        hdc_mem = _gdi32.CreateCompatibleDC(hdc_window)
        bmi = _BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # top-down
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0
        bits = ctypes.c_void_p()
        hbmp = _gdi32.CreateDIBSection(
            hdc_mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0
        )
        if not hbmp or not bits.value:
            _gdi32.DeleteDC(hdc_mem)
            _user32.ReleaseDC(self.hwnd, hdc_window)
            return None
        old = _gdi32.SelectObject(hdc_mem, hbmp)
        try:
            if not _user32.PrintWindow(self.hwnd, hdc_mem, PW_RENDERFULLCONTENT):
                return None
            buf = (ctypes.c_ubyte * (w * h * 4)).from_address(bits.value)
            arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
            return arr[:, :, :3].copy()  # BGRA -> BGR
        finally:
            _gdi32.SelectObject(hdc_mem, old)
            _gdi32.DeleteObject(hbmp)
            _gdi32.DeleteDC(hdc_mem)
            _user32.ReleaseDC(self.hwnd, hdc_window)

    # ------------------------------------------------------------ 点击
    def click(self, x: int, y: int, background: bool = False) -> None:
        """点击窗口内坐标（截图帧里的坐标）。

        background=False：前台模式，窗口最小化先还原，真实点击屏幕坐标。
        background=True：后台模式，PostMessage 鼠标消息，不抢焦点。
        """
        x, y = int(x), int(y)
        if background:
            self._post_click(x, y)
            print(f"[click] 后台消息点击 {self.title or self.hwnd} ({x}, {y})")
            return
        self.restore()
        sx, sy = self.client_to_screen(x, y)
        screen.click(sx, sy, dry_run=False)

    def _post_click(self, x: int, y: int) -> None:
        lparam = (int(y) << 16) | (int(x) & 0xFFFF)
        _user32.PostMessageW(self.hwnd, WM_MOUSEMOVE, 0, lparam)
        _user32.PostMessageW(self.hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(0.08)
        _user32.PostMessageW(self.hwnd, WM_LBUTTONUP, 0, lparam)
