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
DEFAULT_FFMPEG = os.path.join(BIN_DIR, "ffmpeg.exe")


# ---- 純計算函式 ----

def calc_output_duration(start: float, end: float, speed: float) -> float:
    """選取時長除以速度 = 實際輸出時長（秒）。速度 2x → 時長減半。"""
    return (end - start) / speed


def estimate_gif_size(width: int, height: int, fps: int,
                      duration_secs: float, colors: int) -> float:
    """
    GIF 容量粗估（MB）。
    公式：每 frame 平均像素數 × log2(colors)/8 × 壓縮率 × frame 數。
    壓縮率約 0.15（螢幕錄製多為重複區塊）。
    """
    pixels_per_frame = width * height
    bits_per_pixel = math.log2(max(colors, 2))
    bytes_per_frame = pixels_per_frame * bits_per_pixel / 8 * 0.15
    frame_count = fps * duration_secs
    return bytes_per_frame * frame_count / (1024 * 1024)


def estimate_mp4_size(width: int, height: int, fps: int,
                      duration_secs: float, crf: int) -> float:
    """
    MP4 容量粗估（MB）。
    依 CRF 推算目標 bitrate（kbps），再乘時長。
    基準：1080p CRF23 ≈ 2000 kbps，按解析度比例縮放。
    """
    base_pixels = 1920 * 1080
    actual_pixels = width * height
    base_bitrate_kbps = 2000 * (actual_pixels / base_pixels)
    # CRF 每增加 6，bitrate 約減半
    crf_factor = 2 ** ((23 - crf) / 6)
    bitrate_kbps = base_bitrate_kbps * crf_factor
    size_kb = bitrate_kbps * duration_secs / 8
    return size_kb / 1024


# ---- EditorTab UI ----

class EditorTab:
    """影像編輯 Tab 的完整 UI 與邏輯。"""

    PREVIEW_W = 460
    PREVIEW_H = 260

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

        # 載入檔案
        f_load = ttk.LabelFrame(tab, text=" 載入檔案 ", padding=8)
        f_load.pack(fill="x", pady=(0, 8))
        f_load.columnconfigure(0, weight=1)
        self._src_var = tk.StringVar(value="")
        ttk.Entry(f_load, textvariable=self._src_var,
                  state="readonly", width=40).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(f_load, text="開啟", width=6,
                   command=self._open_file).grid(row=0, column=1)
        self._info_label = ttk.Label(f_load, text="", foreground="gray",
                                     font=("Microsoft JhengHei", 9))
        self._info_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # 預覽
        f_preview = ttk.LabelFrame(tab, text=" 預覽 ", padding=8)
        f_preview.pack(fill="x", pady=(0, 8))
        self._canvas = tk.Canvas(f_preview, width=self.PREVIEW_W,
                                 height=self.PREVIEW_H, bg="#1a1a1a",
                                 highlightthickness=0)
        self._canvas.pack()
        self._photo = None
        ctrl_row = ttk.Frame(f_preview)
        ctrl_row.pack(fill="x", pady=(6, 0))
        self._btn_play = ttk.Button(ctrl_row, text="▶ 播放選取範圍",
                                    command=self._toggle_play, state="disabled")
        self._btn_play.pack(side="left")
        self._play_label = ttk.Label(ctrl_row, text="", foreground="gray")
        self._play_label.pack(side="left", padx=8)

        # 裁切範圍
        f_trim = ttk.LabelFrame(tab, text=" 裁切範圍 ", padding=8)
        f_trim.pack(fill="x", pady=(0, 8))
        self._start_var = tk.DoubleVar(value=0.0)
        self._end_var = tk.DoubleVar(value=0.0)

        r0 = ttk.Frame(f_trim); r0.pack(fill="x", pady=2)
        ttk.Label(r0, text="起始：", width=5).pack(side="left")
        self._start_scale = ttk.Scale(r0, variable=self._start_var,
                                      from_=0, to=1, orient="horizontal",
                                      length=300, command=self._on_trim_change)
        self._start_scale.pack(side="left")
        self._start_label = ttk.Label(r0, text="0.0 秒", width=8)
        self._start_label.pack(side="left")

        r1 = ttk.Frame(f_trim); r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="結束：", width=5).pack(side="left")
        self._end_scale = ttk.Scale(r1, variable=self._end_var,
                                    from_=0, to=1, orient="horizontal",
                                    length=300, command=self._on_trim_change)
        self._end_scale.pack(side="left")
        self._end_label = ttk.Label(r1, text="0.0 秒", width=8)
        self._end_label.pack(side="left")

        self._trim_info = ttk.Label(f_trim, text="", foreground="#2980b9")
        self._trim_info.pack(anchor="w")

        # 播放速度
        f_speed = ttk.LabelFrame(tab, text=" 播放速度 ", padding=8)
        f_speed.pack(fill="x", pady=(0, 8))
        self._speed_var = tk.DoubleVar(value=1.0)
        sr = ttk.Frame(f_speed); sr.pack(fill="x")
        for label, val in (("0.25x", 0.25), ("0.5x", 0.5), ("1x", 1.0),
                            ("1.5x", 1.5), ("2x", 2.0)):
            ttk.Radiobutton(sr, text=label, variable=self._speed_var,
                            value=val, command=self._on_trim_change).pack(side="left", padx=4)
        self._duration_label = ttk.Label(f_speed, text="", foreground="gray")
        self._duration_label.pack(anchor="w", pady=(4, 0))

        # 匯出設定
        f_export = ttk.LabelFrame(tab, text=" 匯出設定 ", padding=8)
        f_export.pack(fill="x", pady=(0, 8))
        er = ttk.Frame(f_export); er.pack(fill="x")
        ttk.Label(er, text="輸出格式：").pack(side="left")
        self._export_fmt_var = tk.StringVar(value="source")
        for text, val in (("GIF", "gif"), ("MP4", "mp4"), ("同來源格式", "source")):
            ttk.Radiobutton(er, text=text, variable=self._export_fmt_var,
                            value=val, command=self._update_size_estimate).pack(side="left", padx=4)
        self._size_label = ttk.Label(f_export, text="", foreground="gray",
                                     font=("Microsoft JhengHei", 9))
        self._size_label.pack(anchor="w", pady=(4, 0))

        ttk.Button(tab, text="✂  匯出", command=self._export,
                   state="disabled").pack(ipady=6, pady=(0, 8))
        self._btn_export = tab.winfo_children()[-1]

        # 輸出結果
        self._f_result = ttk.LabelFrame(tab, text=" 輸出結果 ", padding=8)
        self._result_label = ttk.Label(self._f_result, text="")
        self._result_label.pack(anchor="w")
        ttk.Button(self._f_result, text="開啟資料夾",
                   command=self._open_result_folder).pack(pady=(4, 0))
        self._result_path = ""

        self._debounce_job = None

    # ---- 檔案載入 ----

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
                    frame.thumbnail((self.PREVIEW_W, self.PREVIEW_H), Image.LANCZOS)
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
                   f"scale={self.PREVIEW_W}:-2",
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
            foreground="gray"
        )
        self._start_scale.config(to=total)
        self._end_scale.config(to=total)
        self._start_var.set(0.0)
        self._end_var.set(total)
        self._show_frame(0)
        self._btn_play.config(state="normal")
        self._btn_export.config(state="normal")
        self._on_trim_change()

    # ---- 預覽 ----

    def _show_frame(self, idx: int):
        if not self._frames or idx >= len(self._frames):
            return
        img = self._frames[idx].copy()
        img.thumbnail((self.PREVIEW_W, self.PREVIEW_H), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        cx = self.PREVIEW_W // 2
        cy = self.PREVIEW_H // 2
        self._canvas.create_image(cx, cy, anchor="center", image=self._photo)

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

    # ---- 裁切/速度變更 ----

    def _on_trim_change(self, _=None):
        start = self._start_var.get()
        end = self._end_var.get()
        if start >= end and self._frames:
            end = min(start + 0.1, self._total_secs)
            self._end_var.set(end)
        self._start_label.config(text=f"{start:.1f} 秒")
        self._end_label.config(text=f"{end:.1f} 秒")
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

    # ---- 匯出 ----

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
