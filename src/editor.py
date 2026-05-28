"""SnapGIFClip 影像編輯模組：純邏輯 + EditorTab UI。"""
import math
import os
import shutil
import subprocess
import tempfile
import threading

from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, filedialog

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(SCRIPT_DIR, "..", "bin")
_bin_ffmpeg = os.path.join(BIN_DIR, "ffmpeg.exe")
DEFAULT_FFMPEG = _bin_ffmpeg if os.path.exists(_bin_ffmpeg) else (shutil.which("ffmpeg") or _bin_ffmpeg)


def calc_output_duration(start: float, end: float, speed: float) -> float:
    return (end - start) / speed


def estimate_gif_size(width: int, height: int, fps: int,
                      duration_secs: float, colors: int) -> float:
    """GIF 容量粗估（MB）。壓縮率 0.15 適用螢幕錄製（重複色塊多）。"""
    pixels_per_frame = width * height
    bits_per_pixel = math.log2(max(colors, 2))
    bytes_per_frame = pixels_per_frame * bits_per_pixel / 8 * 0.15
    frame_count = fps * duration_secs
    return bytes_per_frame * frame_count / (1024 * 1024)


def estimate_mp4_size(width: int, height: int, fps: int,
                      duration_secs: float, crf: int) -> float:
    """MP4 容量粗估（MB）。基準：1080p CRF23 ≈ 2000 kbps，按解析度比例縮放。"""
    base_pixels = 1920 * 1080
    actual_pixels = width * height
    base_bitrate_kbps = 2000 * (actual_pixels / base_pixels)
    crf_factor = 2 ** ((23 - crf) / 6)  # CRF 每增加 6，bitrate 約減半
    bitrate_kbps = base_bitrate_kbps * crf_factor
    size_kb = bitrate_kbps * duration_secs / 8
    return size_kb / 1024


class TimelineCanvas:
    """影像編輯頁時間軸：Filmstrip 縮圖 + 拖拉選取框。"""

    HANDLE_W = 8     # 把手半寬（px）
    TRACK_H = 55     # 縮圖軌道高度（px）
    TICK_H = 15      # 時間刻度區高度（px）
    THUMB_W = 60     # 目標縮圖寬度（px）

    def __init__(self, parent: tk.Widget, on_range_change):
        self._on_range_change = on_range_change
        self._total: float = 1.0
        self._start: float = 0.0
        self._end: float = 1.0
        self._thumbnails: list = []
        self._source_frames: list = []
        self._fps: int = 0
        self._drag_mode = None
        self._drag_x0: int = 0
        self._drag_s0: float = 0.0
        self._drag_e0: float = 0.0

        self._canvas = tk.Canvas(
            parent,
            height=self.TRACK_H + self.TICK_H,
            bg="#2a2a2a",
            highlightthickness=0,
        )
        self._canvas.pack(fill="x", pady=(0, 4))
        self._canvas.bind("<Configure>", self._on_resize)
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<Motion>", self._on_hover)

    # ── 公開 API ──────────────────────────────────────────────

    def load(self, frames: list, fps: int, total_secs: float) -> None:
        self._source_frames = frames
        self._fps = fps
        self._total = max(total_secs, 0.01)
        self._start = 0.0
        self._end = self._total
        self._regen_and_redraw()

    def set_range(self, start: float, end: float) -> None:
        self._start = start
        self._end = end
        self._draw_overlay()

    # ── 純靜態 helpers（可在無 tkinter 環境下測試）──────────

    @staticmethod
    def time_to_x(t: float, total: float, width: int) -> int:
        if total <= 0 or width <= 0:
            return 0
        return int(t / total * width)

    @staticmethod
    def x_to_time(x: int, total: float, width: int) -> float:
        if total <= 0 or width <= 0:
            return 0.0
        return max(0.0, min(total, x / width * total))

    @staticmethod
    def get_drag_mode(x: int, sx: int, ex: int, handle_w: int):
        if abs(x - sx) <= handle_w:
            return "left"
        if abs(x - ex) <= handle_w:
            return "right"
        if sx + handle_w < x < ex - handle_w:
            return "middle"
        return None

    # ── 私有 helper ───────────────────────────────────────────

    def _w(self) -> int:
        return max(self._canvas.winfo_width(), 1)

    def _regen_and_redraw(self) -> None:
        self._generate_thumbnails()
        self._redraw()

    def _generate_thumbnails(self) -> None:
        frames = self._source_frames
        if not frames:
            self._thumbnails = []
            return
        w = max(self._canvas.winfo_width(), 400)   # 400 為 widget 尚未顯示時的回退值
        n = max(1, w // self.THUMB_W)
        step = max(1, len(frames) // n)
        sampled = frames[::step][:n]
        thumb_w = w // len(sampled)
        self._thumbnails = []
        for frame in sampled:
            img = frame.copy()
            img.thumbnail((thumb_w, self.TRACK_H), Image.LANCZOS)
            self._thumbnails.append(ImageTk.PhotoImage(img))

    def _draw_filmstrip(self) -> None:
        if not self._thumbnails:
            return
        w = self._w()
        thumb_w = w // len(self._thumbnails)
        for i, photo in enumerate(self._thumbnails):
            self._canvas.create_image(i * thumb_w, 0, anchor="nw", image=photo)

    def _draw_tick_marks(self) -> None:
        w = self._w()
        y0 = self.TRACK_H
        intervals = [0.5, 1, 2, 5, 10, 30, 60]
        target_n = max(2, w // 60)
        interval = next(
            (iv for iv in intervals if self._total / iv <= target_n * 2),
            intervals[-1],
        )
        t = 0.0
        while t <= self._total + 0.001:
            x = self.time_to_x(t, self._total, w)
            self._canvas.create_line(x, y0, x, y0 + 5, fill="#888888")
            label = f"{t:.0f}s" if t == int(t) else f"{t:.1f}s"
            self._canvas.create_text(
                x, y0 + 7, text=label,
                fill="#888888", font=("Microsoft JhengHei", 7), anchor="n",
            )
            t = round(t + interval, 3)

    def _redraw(self) -> None:
        self._canvas.delete("all")
        self._draw_filmstrip()
        self._draw_tick_marks()
        self._draw_overlay()

    def _draw_overlay(self) -> None:
        self._canvas.delete("overlay")
        w = self._w()
        h = self.TRACK_H
        sx = self.time_to_x(self._start, self._total, w)
        ex = self.time_to_x(self._end, self._total, w)

        # 非選取區暗化
        if sx > 0:
            self._canvas.create_rectangle(
                0, 0, sx, h,
                fill="#000000", stipple="gray50", tags="overlay")
        if ex < w:
            self._canvas.create_rectangle(
                ex, 0, w, h,
                fill="#000000", stipple="gray50", tags="overlay")
        # 選取區藍色半透明高亮
        self._canvas.create_rectangle(
            sx, 0, ex, h,
            fill="#3498db", stipple="gray25", outline="", tags="overlay")
        # 左把手
        self._canvas.create_rectangle(
            sx - self.HANDLE_W, 0, sx + self.HANDLE_W, h,
            fill="#2980b9", outline="", tags="overlay")
        # 右把手
        self._canvas.create_rectangle(
            ex - self.HANDLE_W, 0, ex + self.HANDLE_W, h,
            fill="#2980b9", outline="", tags="overlay")

    def _on_resize(self, _event) -> None:
        if self._source_frames:
            self._regen_and_redraw()

    def _on_press(self, event) -> None:
        w = self._w()
        sx = self.time_to_x(self._start, self._total, w)
        ex = self.time_to_x(self._end, self._total, w)
        mode = self.get_drag_mode(event.x, sx, ex, self.HANDLE_W)
        if mode is None:
            return
        self._drag_mode = mode
        self._drag_x0 = event.x
        self._drag_s0 = self._start
        self._drag_e0 = self._end

    def _on_drag(self, event) -> None:
        if self._drag_mode is None:
            return
        w = self._w()
        dt = (event.x - self._drag_x0) / w * self._total
        if self._drag_mode == "left":
            self._start = max(0.0, min(round(self._drag_s0 + dt, 2), self._drag_e0 - 0.1))
        elif self._drag_mode == "right":
            self._end = max(self._drag_s0 + 0.1, min(round(self._drag_e0 + dt, 2), self._total))
        elif self._drag_mode == "middle":
            dur = self._drag_e0 - self._drag_s0
            new_s = max(0.0, min(round(self._drag_s0 + dt, 2), self._total - dur))
            self._start = new_s
            self._end = round(new_s + dur, 2)
        self._draw_overlay()
        self._on_range_change(self._start, self._end)

    def _on_release(self, _event) -> None:
        self._drag_mode = None

    def _on_hover(self, event) -> None:
        w = self._w()
        sx = self.time_to_x(self._start, self._total, w)
        ex = self.time_to_x(self._end, self._total, w)
        mode = self.get_drag_mode(event.x, sx, ex, self.HANDLE_W)
        if mode in ("left", "right"):
            self._canvas.config(cursor="sb_h_double_arrow")
        elif mode == "middle":
            self._canvas.config(cursor="fleur")
        else:
            self._canvas.config(cursor="")


class EditorTab:
    """影像編輯 Tab 的完整 UI 與邏輯。"""

    MAX_LOAD_W = 1200   # 載入時最大尺寸（記憶體 vs 品質平衡）
    MAX_LOAD_H = 900

    def __init__(self, parent: tk.Widget, cfg: dict):
        self._parent = parent
        self._cfg = cfg
        self._frames: list = []
        self._total_secs: float = 0.0
        self._fps: int = 15
        self._src_path: str = ""
        self._play_job = None
        self._play_idx = 0
        self._build_ui()

    def _build_ui(self):
        tab = self._parent
        _font = ("Microsoft JhengHei", 13)

        container = ttk.Frame(tab)
        container.pack(fill="both", expand=True)

        left = ttk.Frame(container)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        right = ttk.Frame(container, width=380)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        f_load = ttk.LabelFrame(left, text=" 載入檔案 ", padding=8)
        f_load.pack(fill="x", pady=(0, 6))
        f_load.columnconfigure(0, weight=1)
        self._src_var = tk.StringVar(value="")
        ttk.Entry(f_load, textvariable=self._src_var,
                  state="readonly", font=_font).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(f_load, text="開啟", width=6,
                   command=self._open_file).grid(row=0, column=1)
        self._info_label = ttk.Label(f_load, text="", style="Hint.TLabel")
        self._info_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        f_preview = ttk.LabelFrame(left, text=" 預覽 ", padding=4)
        f_preview.pack(fill="both", expand=True, pady=(0, 6))
        self._canvas = tk.Canvas(f_preview, bg="#1a1a1a", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._photo = None
        self._timeline = TimelineCanvas(
            left,
            on_range_change=self._on_timeline_change,
        )

        ctrl_row = ttk.Frame(left)
        ctrl_row.pack(fill="x", pady=(0, 4))
        self._btn_play = ttk.Button(ctrl_row, text="▶ 播放選取範圍",
                                    command=self._toggle_play, state="disabled")
        self._btn_play.pack(side="left")
        self._play_label = ttk.Label(ctrl_row, text="", style="Hint.TLabel")
        self._play_label.pack(side="left", padx=8)

        f_trim = ttk.LabelFrame(right, text=" 裁切範圍 ", padding=8)
        f_trim.pack(fill="x", pady=(0, 8), padx=4)
        self._start_var = tk.DoubleVar(value=0.0)
        self._end_var = tk.DoubleVar(value=0.0)

        self._start_str = tk.StringVar(value="0.0")
        self._end_str = tk.StringVar(value="0.0")

        for lbl_text, str_var, dbl_var, is_start in (
            ("起始：", self._start_str, self._start_var, True),
            ("結束：", self._end_str, self._end_var, False),
        ):
            row = ttk.Frame(f_trim)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=lbl_text, width=5).pack(side="left")
            ttk.Button(row, text="◀", width=2,
                       command=lambda dv=dbl_var: self._step_time(dv, -0.1)
                       ).pack(side="left")
            entry = ttk.Entry(row, textvariable=str_var, width=6,
                              font=_font, justify="right")
            entry.pack(side="left", padx=2)
            ttk.Label(row, text="秒").pack(side="left")
            ttk.Button(row, text="▶", width=2,
                       command=lambda dv=dbl_var: self._step_time(dv, 0.1)
                       ).pack(side="left")
            entry.bind("<Return>",
                       lambda e, dv=dbl_var, sv=str_var: self._commit_entry(dv, sv, e.widget))
            entry.bind("<FocusOut>",
                       lambda e, dv=dbl_var, sv=str_var: self._commit_entry(dv, sv, e.widget))
            if is_start:
                self._start_entry = entry
            else:
                self._end_entry = entry

        self._trim_info = ttk.Label(f_trim, text="", foreground="#2980b9")
        self._trim_info.pack(anchor="w")

        f_speed = ttk.LabelFrame(right, text=" 播放速度 ", padding=8)
        f_speed.pack(fill="x", pady=(0, 8), padx=4)
        self._speed_var = tk.DoubleVar(value=1.0)
        sr1 = ttk.Frame(f_speed); sr1.pack(fill="x")
        for label, val in (("0.25x", 0.25), ("0.5x", 0.5), ("1x", 1.0)):
            ttk.Radiobutton(sr1, text=label, variable=self._speed_var,
                            value=val, command=self._on_trim_change).pack(side="left", padx=2)
        sr2 = ttk.Frame(f_speed); sr2.pack(fill="x", pady=(2, 0))
        for label, val in (("1.5x", 1.5), ("2x", 2.0)):
            ttk.Radiobutton(sr2, text=label, variable=self._speed_var,
                            value=val, command=self._on_trim_change).pack(side="left", padx=2)
        self._duration_label = ttk.Label(f_speed, text="", style="Hint.TLabel")
        self._duration_label.pack(anchor="w", pady=(4, 0))

        f_export = ttk.LabelFrame(right, text=" 匯出設定 ", padding=8)
        f_export.pack(fill="x", pady=(0, 8), padx=4)
        er = ttk.Frame(f_export); er.pack(fill="x")
        ttk.Label(er, text="格式：").pack(side="left")
        self._export_fmt_var = tk.StringVar(value="source")
        for text, val in (("GIF", "gif"), ("MP4", "mp4"), ("同來源", "source")):
            ttk.Radiobutton(er, text=text, variable=self._export_fmt_var,
                            value=val, command=self._update_size_estimate).pack(side="left", padx=3)
        self._size_label = ttk.Label(f_export, text="", style="Hint.TLabel")
        self._size_label.pack(anchor="w", pady=(4, 0))

        ttk.Button(right, text="✂  匯出", command=self._export,
                   state="disabled").pack(fill="x", ipady=8, pady=(0, 8), padx=4)
        self._btn_export = right.winfo_children()[-1]

        self._f_result = ttk.LabelFrame(right, text=" 輸出結果 ", padding=8)
        self._result_label = ttk.Label(self._f_result, text="")
        self._result_label.pack(anchor="w")
        ttk.Button(self._f_result, text="開啟資料夾",
                   command=self._open_result_folder).pack(pady=(4, 0))
        self._result_path = ""

        self._start_var.trace_add("write", self._on_trim_change)
        self._end_var.trace_add("write", self._on_trim_change)
        self._debounce_job = None

    def _on_timeline_change(self, start: float, end: float) -> None:
        self._start_var.set(round(start, 2))
        self._end_var.set(round(end, 2))

    def _step_time(self, dbl_var: tk.DoubleVar, delta: float) -> None:
        val = round(dbl_var.get() + delta, 1)
        val = max(0.0, min(self._total_secs, val))
        dbl_var.set(val)

    def _commit_entry(self, dbl_var: tk.DoubleVar, str_var: tk.StringVar, widget) -> None:
        try:
            val = float(str_var.get())
            val = max(0.0, min(self._total_secs, round(val, 2)))
            dbl_var.set(val)
        except ValueError:
            widget.configure(foreground="red")
            widget.after(500, lambda: widget.configure(foreground=""))
            str_var.set(f"{dbl_var.get():.1f}")

    def _open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("影像檔案", "*.gif *.mp4"), ("GIF", "*.gif"), ("MP4", "*.mp4")]
        )
        if not path:
            return
        self._src_path = path
        self._src_var.set(path)
        self._info_label.config(text="載入中...", foreground="gray")
        self._frames.clear()
        threading.Thread(target=self._load_frames, args=(path,), daemon=True).start()

    def _load_frames(self, path: str):
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext == ".gif":
                frames, fps = self._load_gif_frames(path)
            else:
                frames, fps = self._load_mp4_frames(path)
            self._frames = frames
            self._fps = fps
            self._total_secs = len(frames) / fps
            self._parent.after(0, self._on_frames_loaded)
        except Exception as e:
            self._parent.after(0, lambda: self._info_label.config(
                text=f"載入失敗：{e}", foreground="red"))

    def _load_gif_frames(self, path: str):
        frames = []
        with Image.open(path) as gif:
            try:
                duration_ms = gif.info.get("duration", 100)
                fps = max(1, int(1000 / duration_ms))
                while True:
                    frame = gif.convert("RGB").copy()
                    frame.thumbnail((self.MAX_LOAD_W, self.MAX_LOAD_H), Image.LANCZOS)
                    frames.append(frame)
                    gif.seek(gif.tell() + 1)
            except EOFError:
                pass
        return frames, fps

    def _load_mp4_frames(self, path: str):
        ffmpeg = DEFAULT_FFMPEG
        tmp_dir = tempfile.mkdtemp()
        try:
            cmd = [ffmpeg, "-i", path, "-vf",
                   f"scale={self.MAX_LOAD_W}:-2",
                   "-r", "15",
                   os.path.join(tmp_dir, "frame_%06d.png"),
                   "-y"]
            subprocess.run(cmd, capture_output=True)
            frame_files = sorted(f for f in os.listdir(tmp_dir) if f.endswith(".png"))
            frames = [Image.open(os.path.join(tmp_dir, f)).copy()
                      for f in frame_files]
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return frames, 15

    def _on_frames_loaded(self):
        if not self._frames:
            return
        w, h = self._frames[0].size
        total = self._total_secs
        self._info_label.config(
            text=f"{os.path.splitext(self._src_path)[1].upper().lstrip('.')}｜"
                 f"{w}×{h}｜{total:.1f} 秒｜{self._fps} fps",
            foreground="",
        )
        self._timeline.load(self._frames, self._fps, self._total_secs)
        self._start_var.set(0.0)
        self._end_var.set(total)
        self._show_frame(0)
        self._btn_play.config(state="normal")
        self._btn_export.config(state="normal")
        self._on_trim_change()

    def _show_frame(self, idx: int):
        if not self._frames or idx >= len(self._frames):
            return
        img = self._frames[idx].copy()
        cw = max(self._canvas.winfo_width(), 200)
        ch = max(self._canvas.winfo_height(), 150)
        img.thumbnail((cw, ch), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, anchor="center", image=self._photo)

    def _toggle_play(self):
        if self._play_job:
            self._parent.after_cancel(self._play_job)
            self._play_job = None
            self._btn_play.config(text="▶ 播放選取範圍")
        else:
            self._btn_play.config(text="⏸ 暫停")
            self._play_idx = self._get_start_frame_idx()
            self._play_next()

    def _play_next(self):
        end_idx = self._get_end_frame_idx()
        if self._play_idx > end_idx:
            self._play_idx = self._get_start_frame_idx()
        self._show_frame(self._play_idx)
        elapsed = self._play_idx / self._fps
        self._play_label.config(
            text=f"{elapsed:.1f} / {self._end_var.get():.1f} 秒")
        self._play_idx += 1
        speed = self._speed_var.get()
        delay = max(10, int(1000 / self._fps / speed))
        self._play_job = self._parent.after(delay, self._play_next)

    def _get_start_frame_idx(self) -> int:
        return max(0, int(self._start_var.get() * self._fps))

    def _get_end_frame_idx(self) -> int:
        return min(len(self._frames) - 1, int(self._end_var.get() * self._fps))

    def _on_trim_change(self, *_):
        start = self._start_var.get()
        end = self._end_var.get()
        if start >= end and self._frames:
            new_end = min(start + 0.1, self._total_secs)
            if new_end != self._end_var.get():
                self._end_var.set(new_end)
            return  # trace 會再次觸發，屆時 start < end
        focused = self._parent.focus_get()
        if focused is not self._start_entry:
            self._start_str.set(f"{start:.1f}")
        if focused is not self._end_entry:
            self._end_str.set(f"{end:.1f}")
        self._timeline.set_range(start, end)
        sel_dur = max(0, end - start)
        speed = self._speed_var.get()
        out_dur = calc_output_duration(start, end, speed)
        self._trim_info.config(text=f"→ 選取時長：{sel_dur:.1f} 秒")
        self._duration_label.config(text=f"→ 實際輸出時長：{out_dur:.1f} 秒")
        self._show_frame(self._get_start_frame_idx())
        if self._debounce_job:
            self._parent.after_cancel(self._debounce_job)
        self._debounce_job = self._parent.after(500, self._update_size_estimate)

    def _update_size_estimate(self, _=None):
        if not self._frames:
            return
        start = self._start_var.get()
        end = self._end_var.get()
        speed = self._speed_var.get()
        out_dur = calc_output_duration(start, end, speed)
        w, h = self._frames[0].size
        fmt = self._export_fmt_var.get()
        if fmt == "source":
            ext = os.path.splitext(self._src_path)[1].lower()
            fmt = "gif" if ext == ".gif" else "mp4"
        cfg = self._cfg
        if fmt == "gif":
            mb = estimate_gif_size(w, h, self._fps, out_dur, cfg["gif"]["colors"])
        else:
            mb = estimate_mp4_size(w, h, self._fps, out_dur, cfg["mp4"]["crf"])
        self._size_label.config(text=f"預估容量：約 {mb:.1f} MB（估算值）")

    def _export(self):
        if not self._frames:
            return
        start_idx = self._get_start_frame_idx()
        end_idx = self._get_end_frame_idx() + 1
        selected = self._frames[start_idx:end_idx]
        if not selected:
            return

        speed = self._speed_var.get()
        fmt = self._export_fmt_var.get()
        if fmt == "source":
            ext = os.path.splitext(self._src_path)[1].lower()
            fmt = "gif" if ext == ".gif" else "mp4"

        base = os.path.splitext(os.path.basename(self._src_path))[0]
        out_folder = self._cfg.get("output_folder", os.path.expanduser("~"))
        out_path = os.path.join(out_folder, f"{base}_edited.{fmt}")

        self._btn_export.config(state="disabled", text="處理中...")
        threading.Thread(
            target=self._do_export,
            args=(selected, fmt, out_path, speed),
            daemon=True,
        ).start()

    def _do_export(self, frames, fmt, out_path, speed):
        from src.recorder import encode_gif, encode_mp4
        try:
            fps_out = max(1, int(self._fps * speed))
            if fmt == "gif":
                encode_gif(frames, out_path, fps_out,
                           self._cfg["gif"]["colors"],
                           self._cfg["gif"]["dithering"])
            else:
                encode_mp4(frames, out_path, fps_out,
                           self._cfg["mp4"]["crf"], DEFAULT_FFMPEG)
            self._result_path = out_path
            self._parent.after(0, self._on_export_done, None)
        except Exception as e:
            self._parent.after(0, self._on_export_done, str(e))

    def _on_export_done(self, error):
        self._btn_export.config(state="normal", text="✂  匯出")
        if error:
            self._result_label.config(text=f"❌ {error}", foreground="red")
        else:
            self._result_label.config(
                text=f"✅ {os.path.basename(self._result_path)}",
                foreground="#27ae60")
        self._f_result.pack(fill="x")

    def _open_result_folder(self):
        folder = os.path.dirname(self._result_path)
        if folder and os.path.exists(folder):
            os.startfile(folder)
