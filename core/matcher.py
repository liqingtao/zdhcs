"""OpenCV 模板匹配与阈值判断（本项目里最核心的一块）。

要回答"画面上到底有没有出现某个按钮"，标准做法是三步：

1. 用 cv2.matchTemplate(screen, template, method) 让模板在整张画面上滑动，
   得到一张同样大小的"相似度热力图"（heat map）。
2. 用 cv2.minMaxLoc 取出热力图里最相似的位置以及对应的分数。
3. 拿这个分数和 threshold 比较，高于阈值才算"找到了"。

不同 method 的语义不一样：
  - TM_CCOEFF_NORMED / TM_CCORR_NORMED：数值越大越相似（本项目默认前者）。
  - TM_SQDIFF / TM_SQDIFF_NORMED：数值越小越相似（0 表示完全一致）。

因此本模块把"分数"统一转成"越大越好"的 score 再和阈值比较，避免记错方向。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple, Union

import cv2
import numpy as np

_METHODS = {
    "TM_SQDIFF": cv2.TM_SQDIFF,
    "TM_SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,
    "TM_CCORR": cv2.TM_CCORR,
    "TM_CCORR_NORMED": cv2.TM_CCORR_NORMED,
    "TM_CCOEFF": cv2.TM_CCOEFF,
    "TM_CCOEFF_NORMED": cv2.TM_CCOEFF_NORMED,
}

# 这两个方法"越小越好"，其余方法"越大越好"。
_SQDIFF_METHODS = {cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED}


@dataclass
class MatchResult:
    """一次模板匹配的结果。"""

    found: bool
    confidence: float  # 统一转成"越大越像"，取值范围大约在 [0, 1] 或 [-1, 1]
    location: Tuple[int, int]  # 模板左上角在画面里的坐标 (x, y)
    size: Tuple[int, int]  # 模板的 (宽, 高)
    method: str

    @property
    def center(self) -> Tuple[int, int]:
        """模板中心的坐标，通常就是点击位置。"""
        x, y = self.location
        w, h = self.size
        return int(x + w / 2), int(y + h / 2)

    def __str__(self) -> str:
        cx, cy = self.center
        state = "命中" if self.found else "未命中"
        return (
            f"MatchResult({state}, confidence={self.confidence:.4f}, "
            f"location={self.location}, center=({cx}, {cy}), method={self.method})"
        )


def load_image(src: Union[str, Path, np.ndarray], flags: int = cv2.IMREAD_COLOR) -> np.ndarray:
    """统一入口：路径则读成 BGR ndarray，ndarray 则原样返回。"""
    if isinstance(src, (str, Path)):
        img = cv2.imread(str(src), flags)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {src}")
        return img
    return np.asarray(src)


def _resolve_method(method: Union[str, int]) -> Tuple[int, str]:
    if isinstance(method, str):
        if method not in _METHODS:
            raise ValueError(f"未知匹配方法: {method}，可选 {sorted(_METHODS)}")
        return _METHODS[method], method
    for name, value in _METHODS.items():
        if value == method:
            return method, name
    raise ValueError(f"未知匹配方法常量: {method}")


def _prepare(
    screen: Union[str, Path, np.ndarray],
    template: Union[str, Path, np.ndarray],
    grayscale: bool,
) -> Tuple[np.ndarray, np.ndarray]:
    screen = load_image(screen)
    template = load_image(template)

    sh, sw = screen.shape[:2]
    th, tw = template.shape[:2]
    if th > sh or tw > sw:
        raise ValueError(f"模板({tw}x{th})不能比画面({sw}x{sh})还大")

    if grayscale:
        if screen.ndim == 3:
            screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        if template.ndim == 3:
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    else:
        # 保证通道数一致，避免 matchTemplate 报错。
        if screen.ndim == 3 and template.ndim == 2:
            template = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)
        elif screen.ndim == 2 and template.ndim == 3:
            screen = cv2.cvtColor(screen, cv2.COLOR_GRAY2BGR)

    return screen, template


def _best(heat: np.ndarray, method: int) -> Tuple[float, Tuple[int, int]]:
    """从热力图中取"最佳匹配"，并把分数统一成越大越好。"""
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(heat)
    if method in _SQDIFF_METHODS:
        return 1.0 - min_val, min_loc
    return max_val, max_loc


def find_template(
    screen: Union[str, Path, np.ndarray],
    template: Union[str, Path, np.ndarray],
    threshold: float = 0.85,
    method: Union[str, int] = "TM_CCOEFF_NORMED",
    grayscale: bool = True,
) -> MatchResult:
    """在画面里找"最像模板"的那一处，并按阈值判断是否命中。"""
    screen, template = _prepare(screen, template, grayscale)
    m, m_name = _resolve_method(method)
    heat = cv2.matchTemplate(screen, template, m)
    score, loc = _best(heat, m)
    th, tw = template.shape[:2]
    return MatchResult(
        found=bool(score >= threshold),
        confidence=float(score),
        location=(int(loc[0]), int(loc[1])),
        size=(int(tw), int(th)),
        method=m_name,
    )


def find_all(
    screen: Union[str, Path, np.ndarray],
    template: Union[str, Path, np.ndarray],
    threshold: float = 0.85,
    method: Union[str, int] = "TM_CCOEFF_NORMED",
    grayscale: bool = True,
    min_distance: int = 20,
) -> List[MatchResult]:
    """找出画面上所有超过阈值的模板位置（贪心 + 局部抑制）。"""
    screen, template = _prepare(screen, template, grayscale)
    m, m_name = _resolve_method(method)
    heat = cv2.matchTemplate(screen, template, m)
    if m in _SQDIFF_METHODS:
        heat = 1.0 - heat

    th, tw = template.shape[:2]
    results: List[MatchResult] = []
    working = heat.copy()
    while True:
        _, max_val, _, max_loc = cv2.minMaxLoc(working)
        if max_val < threshold:
            break
        x, y = max_loc
        results.append(
            MatchResult(
                found=True,
                confidence=float(max_val),
                location=(int(x), int(y)),
                size=(int(tw), int(th)),
                method=m_name,
            )
        )
        # 把附近区域清零，避免同一个按钮被重复报告。
        x0 = max(0, x - min_distance)
        y0 = max(0, y - min_distance)
        x1 = min(working.shape[1], x + tw + min_distance)
        y1 = min(working.shape[0], y + th + min_distance)
        working[y0:y1, x0:x1] = 0.0
    return results


def save_heatmap(
    screen: Union[str, Path, np.ndarray],
    template: Union[str, Path, np.ndarray],
    out_path: Union[str, Path],
    method: Union[str, int] = "TM_CCOEFF_NORMED",
    grayscale: bool = True,
) -> Path:
    """把相似度热力图保存成一张彩色图片，直观看到按钮在画面上的"亮区"。"""
    screen, template = _prepare(screen, template, grayscale)
    m, _ = _resolve_method(method)
    heat = cv2.matchTemplate(screen, template, m)
    if m in _SQDIFF_METHODS:
        heat = 1.0 - heat

    vis = cv2.normalize(heat, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    vis = cv2.applyColorMap(vis, cv2.COLORMAP_JET)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), vis)
    return out_path


def annotate(
    screen: Union[str, Path, np.ndarray],
    results: Union[MatchResult, Sequence[MatchResult]],
    out_path: Union[str, Path, None] = None,
    color: Tuple[int, int, int] = (0, 255, 0),
) -> np.ndarray:
    """在画面上画出匹配框和置信度，便于肉眼核对结果。"""
    img = load_image(screen).copy()
    if isinstance(results, MatchResult):
        results = [results]

    for r in results:
        x, y = r.location
        w, h = r.size
        cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
        cx, cy = r.center
        cv2.circle(img, (cx, cy), 5, color, -1)
        cv2.putText(
            img,
            f"{r.confidence:.3f}",
            (x, max(20, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), img)
    return img

