# -*- coding: utf-8 -*-
"""zdhcs 图形界面：把 PyAutoGUI / OpenCV / Airtest / OCR 串成一个可点击的窗口。

打包后双击 zdhcs.exe 直接打开本窗口，不需要命令行。每个按钮对应 CLI 的一个
子命令，慢操作（OCR / Airtest 首次加载模型）放到后台线程，避免界面卡死。
"""
from __future__ import annotations

import contextlib
import io
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk

import config
from core import matcher, screen


class ZdhcsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("梦幻西游 · 自动化测试 Demo")
        self.root.geometry("760x640")

        self.screen_path: str | None = None
        self.template_path: str | None = None
        self.threshold = tk.DoubleVar(value=config.DEFAULT_THRESHOLD)
        self.method = tk.StringVar(value=config.DEFAULT_METHOD)
        self.real_click = tk.BooleanVar(value=False)
        self._photo = None  # 持有引用，防止预览图被 GC

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # 文件选择区
        file_frame = ttk.LabelFrame(self.root, text="画面 / 模板")
        file_frame.pack(fill="x", **pad)
        ttk.Button(file_frame, text="生成假画面", command=self.on_generate).grid(
            row=0, column=0, **pad
        )
        ttk.Button(file_frame, text="打开画面图…", command=self.on_open_screen).grid(
            row=0, column=1, **pad
        )
        ttk.Button(file_frame, text="打开模板图…", command=self.on_open_template).grid(
            row=0, column=2, **pad
        )
        self.lbl_screen = ttk.Label(file_frame, text="画面：未选择", anchor="w")
        self.lbl_screen.grid(row=1, column=0, columnspan=3, sticky="ew", **pad)
        self.lbl_template = ttk.Label(file_frame, text="模板：未选择", anchor="w")
        self.lbl_template.grid(row=2, column=0, columnspan=3, sticky="ew", **pad)

        # 参数区
        param_frame = ttk.LabelFrame(self.root, text="匹配参数")
        param_frame.pack(fill="x", **pad)
        ttk.Label(param_frame, text="阈值").grid(row=0, column=0, **pad)
        scale = ttk.Scale(
            param_frame,
            from_=0.60,
            to=1.00,
            variable=self.threshold,
            command=lambda _v: self.thresh_lbl.config(
                text=f"{self.threshold.get():.2f}"
            ),
        )
        scale.grid(row=0, column=1, sticky="ew", **pad)
        self.thresh_lbl = ttk.Label(param_frame, text=f"{self.threshold.get():.2f}")
        self.thresh_lbl.grid(row=0, column=2, **pad)
        ttk.Label(param_frame, text="方法").grid(row=0, column=3, **pad)
        ttk.Combobox(
            param_frame,
            textvariable=self.method,
            values=("TM_CCOEFF_NORMED", "TM_CCORR_NORMED", "TM_SQDIFF_NORMED"),
            width=18,
            state="readonly",
        ).grid(row=0, column=4, **pad)
        ttk.Checkbutton(
            param_frame, text="真实点击（默认只打印坐标）", variable=self.real_click
        ).grid(row=0, column=5, **pad)
        param_frame.columnconfigure(1, weight=1)

        # 动作区
        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill="x", **pad)
        ttk.Button(action_frame, text="找图", command=self.on_find).pack(
            side="left", **pad
        )
        ttk.Button(action_frame, text="找图 + 点击", command=self.on_click).pack(
            side="left", **pad
        )
        ttk.Button(action_frame, text="OCR 读文字", command=self.on_ocr).pack(
            side="left", **pad
        )
        ttk.Button(action_frame, text="Airtest 自检", command=self.on_airtest).pack(
            side="left", **pad
        )

        # 预览区
        preview_frame = ttk.LabelFrame(self.root, text="预览")
        preview_frame.pack(fill="both", expand=True, **pad)
        self.preview_label = ttk.Label(preview_frame, text="（找图 / OCR 结果会显示在这里）")
        self.preview_label.pack(fill="both", expand=True, padx=8, pady=8)

        # 日志区
        log_frame = ttk.LabelFrame(self.root, text="日志")
        log_frame.pack(fill="both", **pad)
        self.log_text = tk.Text(log_frame, height=9, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        self.log("就绪。可先点「生成假画面」，再点「找图 / OCR / Airtest 自检」。")

    # -------------------------------------------------------------- helpers
    def log(self, msg: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _run_async(self, fn, on_done=None) -> None:
        """在后台线程执行 fn()，完成后回到主线程调用 on_done(result, error)。"""

        def _worker() -> None:
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                self.root.after(0, lambda: on_done(None, exc) if on_done else None)
                return
            self.root.after(0, lambda: on_done(result, None) if on_done else None)

        threading.Thread(target=_worker, daemon=True).start()

    def _require_screen(self) -> bool:
        if not self.screen_path:
            messagebox.showwarning("提示", "请先选择画面图，或点「生成假画面」。")
            return False
        return True

    def _require_template(self) -> bool:
        if not self.template_path:
            messagebox.showwarning("提示", "请先选择模板图，或点「生成假画面」。")
            return False
        return True

    def _load_bgr(self, path: str):
        return matcher.load_image(path)

    def _show_preview(self, bgr) -> None:
        """把 BGR ndarray 转成可显示的缩略图。"""
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        pil.thumbnail((620, 360), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(pil)
        self.preview_label.configure(image=self._photo, text="")

    @staticmethod
    def _capture_stdout(fn):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = fn()
        return result, buf.getvalue().strip()

    # ---------------------------------------------------------------- events
    def on_generate(self) -> None:
        def _run():
            from demos.make_fake_screen import main as generate

            return self._capture_stdout(generate)

        def _done(res, err):
            if err:
                self.log(f"[生成] 失败: {err}")
                messagebox.showerror("错误", str(err))
                return
            paths, text = res
            self.screen_path = str(paths["screen"])
            self.template_path = str(paths["btn_start"])
            self.lbl_screen.config(text=f"画面：{self.screen_path}")
            self.lbl_template.config(text=f"模板：{self.template_path}")
            if text:
                self.log("[生成]\n" + text)
            self.log("[生成] 完成，已自动选中假画面和「开始任务」模板。")
            self._show_preview(self._load_bgr(self.screen_path))

        self._run_async(_run, _done)

    def on_open_screen(self) -> None:
        path = filedialog.askopenfilename(
            title="选择画面图",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp"), ("所有文件", "*.*")],
        )
        if not path:
            return
        self.screen_path = path
        self.lbl_screen.config(text=f"画面：{path}")
        self.log(f"[打开画面] {path}")
        self._show_preview(self._load_bgr(path))

    def on_open_template(self) -> None:
        path = filedialog.askopenfilename(
            title="选择模板图",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp"), ("所有文件", "*.*")],
        )
        if not path:
            return
        self.template_path = path
        self.lbl_template.config(text=f"模板：{path}")
        self.log(f"[打开模板] {path}")

    def on_find(self) -> None:
        if not self._require_screen() or not self._require_template():
            return
        threshold = self.threshold.get()
        method = self.method.get()

        def _run():
            frame = self._load_bgr(self.screen_path)
            result = matcher.find_template(
                frame, self.template_path, threshold=threshold, method=method
            )
            annotated = matcher.annotate(frame, result)
            return frame, result, annotated

        def _done(res, err):
            if err:
                self.log(f"[找图] 出错: {err}")
                messagebox.showerror("错误", str(err))
                return
            _, result, annotated = res
            self.log(f"[找图] {result}")
            if result.found:
                self.log(f"[找图] 命中中心点 {result.center}，可用于点击。")
            self._show_preview(annotated)

        self._run_async(_run, _done)

    def on_click(self) -> None:
        if not self._require_screen() or not self._require_template():
            return
        threshold = self.threshold.get()
        real = self.real_click.get()

        def _run():
            frame = self._load_bgr(self.screen_path)
            result = matcher.find_template(frame, self.template_path, threshold=threshold)
            if not result.found:
                return frame, result, "未找到按钮，跳过点击。"
            x, y = result.center
            _, click_text = self._capture_stdout(
                lambda: screen.click(x, y, dry_run=not real)
            )
            return frame, result, click_text

        def _done(res, err):
            if err:
                self.log(f"[点击] 出错: {err}")
                messagebox.showerror("错误", str(err))
                return
            frame, result, text = res
            self.log(f"[点击] {result}")
            if text:
                self.log("[点击] " + text)
            annotated = matcher.annotate(frame, result)
            self._show_preview(annotated)

        self._run_async(_run, _done)

    def on_ocr(self) -> None:
        if not self._require_screen():
            return

        def _run():
            from core.ocr import create_engine

            engine = create_engine()
            img = self._load_bgr(self.screen_path)
            results = engine.read_text(img)
            return engine, img, results

        def _done(res, err):
            if err:
                self.log(f"[OCR] 出错: {err}")
                messagebox.showerror("错误", str(err))
                return
            _, img, results = res
            if not results:
                self.log("[OCR] 未识别到文字。")
            else:
                self.log("[OCR] 识别结果：")
                for r in results:
                    conf = f"{r.confidence:.3f}" if r.confidence is not None else "n/a"
                    self.log(f"    {r.text}  ({conf})")
            self._show_preview(img)

        self._run_async(_run, _done)

    def on_airtest(self) -> None:
        if not self._require_screen() or not self._require_template():
            return
        threshold = self.threshold.get()

        def _run():
            from airtest.core.api import Template

            img = self._load_bgr(self.screen_path)
            template = Template(self.template_path, threshold=threshold)
            hit = template.match_in(img)
            return img, hit

        def _done(res, err):
            if err:
                self.log(f"[Airtest] 出错: {err}")
                messagebox.showerror("错误", str(err))
                return
            img, hit = res
            if hit is None:
                self.log("[Airtest] Template.match_in 未命中。")
            else:
                self.log(f"[Airtest] 命中，点击坐标 {hit}（等价 assert_exists 为真）")
            self._show_preview(img)

        self._run_async(_run, _done)


def main() -> None:
    root = tk.Tk()
    ZdhcsApp(root)

    def _report_exc(exc_type, exc_value, exc_tb):
        messagebox.showerror("程序错误", f"{exc_type.__name__}: {exc_value}")

    root.report_callback_exception = _report_exc
    root.mainloop()


if __name__ == "__main__":
    main()
