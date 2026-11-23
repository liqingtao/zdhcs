"""验证 core.matcher 的核心逻辑（纯 OpenCV，无 GUI，可离线运行）。"""

import numpy as np
import pytest

from core.matcher import find_all, find_template


def _button_pattern(w: int, h: int, channels: int = 1) -> np.ndarray:
    """生成一块固定、带纹理的"按钮"图案（随机但可复现）。

    用随机纹理而不是纯色块，是因为纯色块方差为 0，会让 TM_CCOEFF_NORMED
    这类归一化方法退化；真实按钮总有文字/边框，本来就带纹理。
    """
    rng = np.random.default_rng(123)
    if channels == 1:
        return rng.integers(30, 255, (h, w), dtype=np.uint8)
    return rng.integers(30, 255, (h, w, channels), dtype=np.uint8)


def _make_screen(size=(200, 150), buttons=((50, 40, 40, 30),)) -> np.ndarray:
    """生成一张带噪声背景的画面，并在指定位置贴按钮图案。"""
    rng = np.random.default_rng(0)
    screen = rng.integers(20, 80, (size[1], size[0]), dtype=np.uint8)
    for x, y, w, h in buttons:
        screen[y : y + h, x : x + w] = _button_pattern(w, h)
    return screen


def _template_from(screen, x, y, w, h):
    return screen[y : y + h, x : x + w].copy()


def test_find_template_hits_perfect_match():
    screen = _make_screen()
    template = _template_from(screen, 50, 40, 40, 30)

    result = find_template(screen, template, threshold=0.85)

    assert result.found is True
    assert result.location == (50, 40)
    assert result.center == (70, 55)
    assert result.confidence > 0.99


def test_find_template_below_threshold_is_not_found():
    screen = _make_screen()
    template = _template_from(screen, 50, 40, 40, 30)

    result = find_template(screen, template, threshold=2.0)

    assert result.found is False
    assert result.confidence > 0.99  # 相似度本身很高，只是阈值没到


def test_find_template_sqdiff_method():
    screen = _make_screen()
    template = _template_from(screen, 50, 40, 40, 30)

    result = find_template(screen, template, threshold=0.85, method="TM_SQDIFF_NORMED")

    assert result.found is True
    assert result.location == (50, 40)
    assert result.confidence > 0.99


def test_find_all_returns_multiple_matches():
    buttons = ((40, 30, 30, 20), (130, 90, 30, 20))
    screen = _make_screen(buttons=buttons)
    template = _template_from(screen, 40, 30, 30, 20)

    results = find_all(screen, template, threshold=0.85, min_distance=10)

    assert len(results) == 2
    locations = sorted(r.location for r in results)
    assert locations == [(40, 30), (130, 90)]


def test_template_larger_than_screen_raises():
    screen = _make_screen()
    template = np.full((300, 300), 255, dtype=np.uint8)

    with pytest.raises(ValueError):
        find_template(screen, template)


def test_color_matching_without_grayscale():
    rng = np.random.default_rng(1)
    screen = rng.integers(20, 80, (150, 200, 3), dtype=np.uint8)
    screen[40:70, 50:90] = _button_pattern(40, 30, channels=3)
    template = screen[40:70, 50:90].copy()

    result = find_template(screen, template, threshold=0.85, grayscale=False)

    assert result.found is True
    assert result.location == (50, 40)

