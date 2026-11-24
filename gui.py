# -*- coding: utf-8 -*-
"""zdhcs 托管图形界面：按功能划分页面，一键开始 / 取消，真实点击默认开启。

页面结构：
    托管窗口 —— 绑定一个游戏窗口（hwnd），截图与点击只作用于它，多开互不影响。
    选项     —— 真实点击（默认开）、后台点击（PostMessage 不抢焦点）、阈值/方法。
    功能页   —— 打图 / 刷经验 / 跑商，每页独立轮数与「开始 / 取消」。
    工具箱   —— 离线演示：生成假画面 / 截屏 / 找图 / OCR / Airtest 自检。

托管窗口在后台时：截图走 PrintWindow（不抢焦点）；点击默认前台模式（最小化
自动还原后真点），勾选「后台点击」则用 PostMessage 直接发消息给窗口。
任务开始时若不在功能页面，会点导航锚点（任务追踪 NPC 名）自动寻路再执行。
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
from core.window import WindowTarget, list_windows
from run_datu import run_datu
from run_juqing import run_juqing
from run_paoshang import run_paoshang
from run_shuajingyan import run_shuajingyan


TASKS = {
    "datu": ("打图", run_datu, "领取任务按钮 btn_take_task"),
    "shuajingyan": ("刷经验", run_shuajingyan, "开始刷怪按钮 btn_start_grind"),
    "paoshang": ("跑商", run_paoshang, "城市 OCR（买入城 / 卖出城）"),
    "juqing": ("新号剧情", run_juqing, "任务追踪 NPC 名 nav_quest_npc"),
}


class ZdhcsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("梦幻西游 · 自动化托管")
        self.root.geometry("880x800")

        self.screen_path: str | None = None
        self.template_path: str | None = None
        self.threshold = tk.DoubleVar(value=config.DEFAULT_THRESHOLD)
        self.method = tk.StringVar(value=config.DEFAULT_METHOD)
        self.real_click = tk.BooleanVar(value=True)  # 默认开启真实点击
        self.background_mode = tk.BooleanVar(value=False)
        self.windows: dict[str, int] = {}
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.task_vars: dict[str, dict] = {}
        self._photo = None  # 持有引用，防止预览图被 GC

        self._build_ui()
        self.on_refresh_windows()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # 托管窗口
        win_frame = ttk.LabelFrame(
            self.root, text="托管窗口（截图与点击只作用于它，多开互不影响）"
        )
        win_frame.pack(fill="x", **pad)
        self.win_combo = ttk.Combobox(win_frame, state="readonly")
        self.win_combo.grid(row=0, column=0, padx=8, pady=6, sticky="ew")
        self.win_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_target_label())
        ttk.Button(win_frame, text="刷新", command=self.on_refresh_windows).grid(
            row=0, column=1, padx=4
        )
        ttk.Button(win_frame, text="预览窗口画面", command=self.on_preview_target).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(win_frame, text="截取模板参考图", command=self.on_capture_for_template).grid(
            row=0, column=3, padx=4
         )
        self.lbl_target = ttk.Label(win_frame, text="当前托管窗口：未选择", anchor="w")
        self.lbl_target.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8)
        win_frame.columnconfigure(0, weight=1)

        # 选项
        opt_frame = ttk.LabelFrame(self.root, text="选项")
        opt_frame.pack(fill="x", **pad)
        ttk.Checkbutton(
            opt_frame, text="真实点击（取消勾选则干跑只打印坐标）", variable=self.real_click
        ).grid(row=0, column=0, padx=8, sticky="w")
        ttk.Checkbutton(
            opt_frame, text="后台点击（PostMessage 不抢焦点）", variable=self.background_mode
        ).grid(row=0, column=1, padx=8, sticky="w")
        ttk.Label(opt_frame, text="阈值").grid(row=0, column=2, padx=(12, 0))
        scale = ttk.Scale(
            opt_frame,
            from_=0.60,
            to=1.00,
            variable=self.threshold,
            command=lambda _v: self.thresh_lbl.config(text=f"{self.threshold.get():.2f}"),
        )
        scale.grid(row=0, column=3, sticky="ew", padx=6)
        self.thresh_lbl = ttk.Label(opt_frame, text=f"{self.threshold.get():.2f}")
        self.thresh_lbl.grid(row=0, column=4, padx=(0, 8))
        opt_frame.columnconfigure(3, weight=1)

        # 功能页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="x", **pad)
        for key, (name, _fn, hint) in TASKS.items():
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=name)
            self._build_task_tab(frame, key, hint)

        tool_frame = ttk.Frame(self.notebook)
        self.notebook.add(tool_frame, text="工具箱")
        self._build_tool_tab(tool_frame)

        # 预览
        preview_frame = ttk.LabelFrame(self.root, text="预览")
        preview_frame.pack(fill="both", expand=True, **pad)
        self.preview_label = ttk.Label(
            preview_frame, text="（托管窗口画面 / 找图 / OCR 结果会显示在这里）"
        )
        self.preview_label.pack(fill="both", expand=True, padx=8, pady=8)

        # 日志
        log_frame = ttk.LabelFrame(self.root, text="日志")
        log_frame.pack(fill="both", **pad)
        self.log_text = tk.Text(log_frame, height=8, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        self.log("就绪。先「刷新」并选择托管窗口，再到对应功能页点「开始」；「取消」随时停止。")

    def _build_task_tab(self, frame: ttk.Frame, key: str, hint: str) -> None:
        row = ttk.Frame(frame)
        row.pack(fill="x", padx=8, pady=6)
        ttk.Label(row, text="轮数").pack(side="left")
        rounds = tk.IntVar(value=3)
        ttk.Spinbox(row, from_=1, to=99, width=5, textvariable=rounds).pack(
            side="left", padx=6
        )
        start = ttk.Button(row, text="开始", command=lambda: self.on_start_task(key))
        start.pack(side="left", padx=20)
        ttk.Button(row, text="取消", command=self.on_cancel_task).pack(side="left")
        status = ttk.Label(frame, text="状态：空闲", anchor="w")
        status.pack(fill="x", padx=8)
        ttk.Label(
            frame,
            text=f"入口锚点：{hint}。不在页面时会点导航锚点（nav_quest_npc）自动寻路。",
            anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 6))
        self.task_vars[key] = {"rounds": rounds, "status": status, "start": start}

    def _build_tool_tab(self, frame: ttk.Frame) -> None:
        pad = {"padx": 8, "pady": 4}
        file_frame = ttk.LabelFrame(frame, text="画面 / 模板（离线演示）")
        file_frame.pack(fill="x", **pad)
        ttk.Button(file_frame, text="生成假画面", command=self.on_generate).grid(
            row=0, column=0, **pad
        )
        ttk.Button(file_frame, text="截取屏幕", command=self.on_capture_screen).grid(
            row=0, column=1, **pad
        )
        ttk.Button(file_frame, text="打开画面图…", command=self.on_open_screen).grid(
            row=0, column=2, **pad
        )
        ttk.Button(file_frame, text="打开模板图…", command=self.on_open_template).grid(
            row=0, column=3, **pad
        )
        self.lbl_screen = ttk.Label(file_frame, text="画面：未选择", anchor="w")
        self.lbl_screen.grid(row=1, column=0, columnspan=4, sticky="ew", **pad)
        self.lbl_template = ttk.Label(file_frame, text="模板：未选择", anchor="w")
        self.lbl_template.grid(row=2, column=0, columnspan=4, sticky="ew", **pad)

        action_frame = ttk.Frame(frame)
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

    # -------------------------------------------------------------- helpers
    def log(self, msg: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _run_async(self, fn, on_done=None) -> None:
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

    def _update_target_label(self, title: str | None = None) -> None:
        title = title if title is not None else self.win_combo.get()
        if title and title in self.windows:
            self.lbl_target.config(
                text=f"当前托管窗口：{title} (hwnd={self.windows[title]})"
            )
        else:
            self.lbl_target.config(text="当前托管窗口：未选择")

    # ---------------------------------------------------------- 托管窗口
    def on_refresh_windows(self) -> None:
        self.windows = {title: hwnd for hwnd, title in list_windows()}
        titles = list(self.windows)
        self.win_combo.config(values=titles)
        candidates = [t for t in titles if "梦幻" in t]
        guess = None
        if candidates:
            online = [t for t in candidates if "ONLINE" in t.upper()]
            # 优先选主客户端（标题含 ONLINE），否则取标题最长的一个。
            guess = online[0] if online else max(candidates, key=len)
        if guess:
            self.win_combo.set(guess)
        elif titles:
            self.win_combo.set(titles[0])
        else:
            self.win_combo.set("")
        self._update_target_label()
        self.log(f"[窗口] 枚举到 {len(titles)} 个可见窗口")

    def on_preview_target(self) -> None:
        title = self.win_combo.get()
        if not title or title not in self.windows:
            messagebox.showwarning("提示", "请先选择托管窗口。")
            return
        try:
            target = WindowTarget(self.windows[title])
            frame = target.screenshot()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("错误", str(exc))
            return
        self._update_target_label(title)
        self.log(f"[预览] {title}（{frame.shape[1]}x{frame.shape[0]}）")
        self._show_preview(frame)

    def on_capture_for_template(self) -> None:
        """截取托管窗口画面到 assets/screenshots/，方便用 capture_template 裁模板。"""
        title = self.win_combo.get()
        if not title or title not in self.windows:
            messagebox.showwarning("提示", "请先选择托管窗口。")
            return
        try:
            target = WindowTarget(self.windows[title])
            target.activate()
            import time as _t
            _t.sleep(0.3)
            frame = target.screenshot()
            out = config.SCREENSHOTS_DIR / "template_ref.png"
            import cv2 as _cv2
            out.parent.mkdir(parents=True, exist_ok=True)
            _cv2.imwrite(str(out), frame)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("错误", str(exc))
            return
        self.screen_path = str(out)
        self.lbl_screen.config(text=f"画面：{out}（模板参考截图）")
        self.log(f"[截取] 模板参考图已保存: {out}")
        self._show_preview(frame)

    # ---------------------------------------------------------- 开始/取消
    def on_start_task(self, key: str) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showwarning("提示", "已有任务在运行，请先「取消」。")
            return
        title = self.win_combo.get()
        if not title or title not in self.windows:
            messagebox.showwarning("提示", "请先在「托管窗口」选择目标窗口。")
            return
        self.cancel_event.clear()
        try:
            target = WindowTarget(self.windows[title])
        except ValueError as exc:
            messagebox.showerror("错误", str(exc))
            return
        rounds = int(self.task_vars[key]["rounds"].get())
        dry_run = not self.real_click.get()
        background = self.background_mode.get()
        name = TASKS[key][0]

        def log(msg: str) -> None:
            self.root.after(0, self.log, msg)

        def click(x: int, y: int) -> None:
            target.click(x, y, background=background)

        def worker() -> None:
            try:
                log(f"[启动] 任务：{name} | 托管窗口：{target.title} (hwnd={target.hwnd})")
                # 把游戏窗口带到前台，确保 PrintWindow 截到的是游戏画面、
                # 前台点击打到正确坐标。后台点击模式下也先激活一次，之后
                # PostMessage 不再抢焦点。
                target.activate()
                log(f"[窗口] 已激活托管窗口：{target.title}")
                if dry_run:
                    log("[提示] 未勾选「真实点击」，本轮干跑只打印坐标")
                TASKS[key][1](
                    rounds,
                    dry_run=dry_run,
                    screenshot=target.screenshot,
                    click=click,
                    log=log,
                    should_stop=self.cancel_event.is_set,
                )
                log(f"[结束] {name} 任务结束")
            except Exception as exc:  # noqa: BLE001
                log(f"[错误] {type(exc).__name__}: {exc}")
            finally:
                self.root.after(0, self._task_done, key)

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()
        self.task_vars[key]["status"].config(text=f"状态：运行中（{name}）")
        for widgets in self.task_vars.values():
            widgets["start"].config(state="disabled")

    def on_cancel_task(self) -> None:
        if self.worker is None or not self.worker.is_alive():
            self.log("[取消] 当前没有运行中的任务。")
            return
        self.cancel_event.set()
        self.log("[取消] 已请求停止，等待当前等待步骤退出…")

    def _task_done(self, key: str) -> None:
        for widgets in self.task_vars.values():
            widgets["start"].config(state="normal")
            widgets["status"].config(text="状态：空闲")

    # -------------------------------------------------------------- 工具箱
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

    def on_capture_screen(self) -> None:
        def _run():
            return screen.screenshot(path=config.SCREENSHOTS_DIR / "live_screen.png")

        def _done(res, err):
            if err:
                self.log(f"[截屏] 失败: {err}")
                messagebox.showerror("错误", str(err))
                return
            self.screen_path = str(config.SCREENSHOTS_DIR / "live_screen.png")
            self.lbl_screen.config(text=f"画面：{self.screen_path}（实时截屏）")
            self.log("[截屏] 已截取当前屏幕。")
            self._show_preview(res)

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
        if not self._require_template():
            return
        real = self.real_click.get()
        if not real and not self._require_screen():
            return
        threshold = self.threshold.get()
        source = self.screen_path
        title = self.win_combo.get()
        target = None
        if title and title in self.windows:
            try:
                target = WindowTarget(self.windows[title])
            except ValueError:
                target = None

        def _run():
            if real:
                if target is not None:
                    frame = target.screenshot()
                else:
                    frame = screen.screenshot(
                        path=config.SCREENSHOTS_DIR / "live_screen.png"
                    )
            else:
                frame = self._load_bgr(source)
            result = matcher.find_template(frame, self.template_path, threshold=threshold)
            if not result.found:
                return frame, result, "未找到按钮，跳过点击。"
            x, y = result.center
            if real:
                if target is not None:
                    target.click(x, y, background=self.background_mode.get())
                    click_text = f"已真实点击托管窗口 ({x}, {y})"
                else:
                    screen.click(x, y, dry_run=False)
                    click_text = f"已真实点击屏幕 ({x}, {y})（基于实时截屏匹配）"
            else:
                _, click_text = self._capture_stdout(
                    lambda: screen.click(x, y, dry_run=True)
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
