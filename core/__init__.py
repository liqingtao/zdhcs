"""核心能力：屏幕 I/O、OpenCV 模板匹配、OCR 封装。"""

from .matcher import MatchResult, find_all, find_template, load_image

__all__ = ["MatchResult", "find_all", "find_template", "load_image"]

