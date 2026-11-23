"""PaddleOCR 封装：从画面里读文字（倒计时、任务状态等）。

注意两点：
1. 首次运行会联网下载模型（几百 MB），需要能访问外网。
2. paddleocr 2.x 和 3.x 的返回结构不一样，这里做了兼容，但 3.x 改动较大，
   建议先按 requirements-ocr.txt 里的 2.x 版本装，能跑通再考虑升级。
"""
from dataclasses import dataclass
from pathlib import Path
from importlib import util as _importlib_util
from typing import List, Optional, Union

import numpy as np


@dataclass
class TextResult:
    """一行被识别出来的文字。"""

    text: str
    confidence: Optional[float]
    box: Optional[np.ndarray]  # 四点坐标（多边形），可能是 None

    def __str__(self) -> str:
        conf = f"{self.confidence:.3f}" if self.confidence is not None else "n/a"
        return f"TextResult(text={self.text!r}, confidence={conf})"


class OcrEngine:
    """PaddleOCR 的懒加载封装，真正用到时才初始化模型。"""

    def __init__(self, lang: str = "ch", use_angle_cls: bool = True, use_gpu: bool = False):
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.use_gpu = use_gpu
        self._engine = None

    def _ensure_engine(self):
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise ImportError(
                    "未安装 paddleocr，请先执行: pip install -r requirements-ocr.txt"
                ) from exc
            self._engine = PaddleOCR(
                use_angle_cls=self.use_angle_cls,
                lang=self.lang,
                use_gpu=self.use_gpu,
                show_log=False,
            )
        return self._engine

    def read_text(
        self,
        image: Union[str, Path, np.ndarray],
    ) -> List[TextResult]:
        """识别一张图里的所有文字，返回 TextResult 列表。"""
        engine = self._ensure_engine()
        raw = engine.ocr(image, cls=self.use_angle_cls)
        return self._flatten(raw)

    def _flatten(self, raw) -> List[TextResult]:
        items: List[TextResult] = []
        if not raw:
            return items

        # PaddleOCR >= 3.0：predict() 返回 [ {rec_texts, rec_scores, ...}, ... ]。
        if isinstance(raw[0], dict):
            for result in raw:
                texts = result.get("rec_texts") or []
                scores = result.get("rec_scores") or []
                polys = result.get("rec_polys") or result.get("dt_polys") or []
                for i, text in enumerate(texts):
                    items.append(
                        TextResult(
                            text=str(text),
                            confidence=float(scores[i]) if i < len(scores) else None,
                            box=np.asarray(polys[i]) if i < len(polys) else None,
                        )
                    )
            return items

        # PaddleOCR 2.x：ocr() 返回 [[ [box, (text, conf)], ... ], ... ]。
        for page in raw:
            for line in page or []:
                if not line:
                    continue
                box, text_conf = line[0], line[1]
                text, conf = text_conf[0], text_conf[1]
                items.append(
                    TextResult(
                        text=str(text),
                        confidence=float(conf),
                        box=np.asarray(box),
                    )
                )
        return items


class RapidOcrEngine:
    """rapidocr_onnxruntime 的轻量封装，接口和 OcrEngine 对齐。

    PaddleOCR/PaddlePaddle 在 macOS 上依赖树较重，rapidocr（onnxruntime）跨平台
    更省事，适合本机验证"读文字"这条链路。两者返回的 TextResult 结构一致。
    """

    def __init__(self):
        self._engine = None

    def _ensure_engine(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as exc:
                raise ImportError(
                    "未安装 rapidocr_onnxruntime，请先执行: pip install -r requirements-ocr-rapid.txt"
                ) from exc
            # 首次实例化会自动下载/加载 ONNX 模型。
            self._engine = RapidOCR()
        return self._engine

    def read_text(self, image: Union[str, Path, np.ndarray]) -> List[TextResult]:
        engine = self._ensure_engine()
        src = str(image) if isinstance(image, (str, Path)) else image
        result, _elapse = engine(src)
        items: List[TextResult] = []
        for line in result or []:
            box, text, score = line[0], line[1], line[2]
            items.append(
                TextResult(
                    text=str(text),
                    confidence=float(score),
                    box=np.asarray(box),
                )
            )
        return items


def create_engine(prefer: str = "paddle"):
    """按可用性返回一个 OCR 引擎：优先 PaddleOCR，其次 rapidocr。"""
    if prefer == "paddle" and _importlib_util.find_spec("paddleocr") is not None:
        return OcrEngine()
    if _importlib_util.find_spec("rapidocr_onnxruntime") is not None:
        return RapidOcrEngine()
    if _importlib_util.find_spec("paddleocr") is not None:
        return OcrEngine()
    raise ImportError(
        "未安装任何 OCR 引擎：请安装 PaddleOCR 或 rapidocr_onnxruntime 之一。"
    )


def find_text(
    image: Union[str, Path, np.ndarray],
    keyword: str,
    engine=None,
) -> List[TextResult]:
    """在一张图里查找包含 keyword 的文字，返回命中的结果。"""
    engine = engine or create_engine()
    results = engine.read_text(image)
    return [r for r in results if keyword in r.text]

