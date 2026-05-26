"""SnapGIFClip 主程式。"""
import ctypes
import os
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import src.config as config

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


def show_cth_banner():
    b = "\033[90m"
    c = "\033[96m"
    y = "\033[93m"
    r = "\033[0m"
    print(f"{b}/*  ================================  *\\{r}")
    print(f"{b} *                                    *{r}")
    print(f"{b} *    {c}██████╗████████╗██╗  ██╗{b}        *{r}")
    print(f"{b} *   {c}██╔════╝   ██║   ██║  ██║{b}        *{r}")
    print(f"{b} *   {c}██║        ██║   ███████║{b}        *{r}")
    print(f"{b} *   {c}██║        ██║   ██╔══██║{b}        *{r}")
    print(f"{b} *   {c}╚██████╗   ██║   ██║  ██║{b}        *{r}")
    print(f"{b} *    {c}╚═════╝   ╚═╝   ╚═╝  ╚═╝{b}        *{r}")
    print(f"{b} *                                    *{r}")
    print(f"{b} *          {y}created by CTH{b}            *{r}")
    print(f"{b}\\*  ================================  */{r}")
    print()


class SnapGIFClipApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SnapGIFClip")
        self.root.resizable(True, True)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = int(sw * 0.80)
        h = int(sh * 0.83)
        self.root.minsize(int(sw * 0.46), int(sh * 0.50))
        self.root.geometry(f"{w}x{h}")

        self.msg_queue: queue.Queue = queue.Queue()
        self._recorder = None
        self._border = None
        self._listener = None
        self._cfg = config.load()

        try:
            import sv_ttk
            sv_ttk.set_theme("light")
        except ImportError:
            pass

        self._apply_styles()
        self._build_ui()
        self._start_hotkey_listener(self._cfg["hotkey"])
        self._poll_queue()

    # ---- 樣式 ----

    def _apply_styles(self):
        from tkinter import font as tkfont
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
            try:
                tkfont.nametofont(name).configure(family="Microsoft JhengHei", size=13)
            except Exception:
                pass

        style = ttk.Style()
        font_main = ("Microsoft JhengHei", 13)
        font_hint = ("Microsoft JhengHei", 11)
        style.configure("TButton",            font=font_main)
        style.configure("TEntry",             font=font_main)
        style.configure("TCombobox",          font=font_main)
        style.configure("TSpinbox",           font=font_main)
        style.configure("TLabel",             font=font_main)
        style.configure("TCheckbutton",       font=font_main)
        style.configure("TRadiobutton",       font=font_main)
        style.configure("TLabelframe.Label",  font=font_main, foreground="#1A6BAF")
        style.configure("TNotebook.Tab",      font=font_main)
        style.configure("Hint.TLabel",        font=font_hint, foreground="#888888")

    # ---- UI ----

    def _build_ui(self):
        self._notebook = ttk.Notebook(self.root)
        self._notebook.pack(fill="both", expand=True, padx=12, pady=(8, 0))

        self._tab_main = ttk.Frame(self._notebook, padding=10)
        self._tab_editor = ttk.Frame(self._notebook, padding=10)
        self._tab_settings = ttk.Frame(self._notebook, padding=10)

        self._notebook.add(self._tab_main,     text="  主要工作  ")
        self._notebook.add(self._tab_editor,   text="  影像編輯  ")
        self._notebook.add(self._tab_settings, text="  設定  ")

        self._build_main_tab()
        self._build_settings_tab()
        self._build_editor_tab()

    # ================================================================
    # 設定 Tab
    # ================================================================

    def _build_settings_tab(self):
        tab = self._tab_settings

        # 輸出資料夾
        f_folder = ttk.LabelFrame(tab, text=" 輸出資料夾 ", padding=8)
        f_folder.pack(fill="x", pady=(0, 10))
        f_folder.columnconfigure(0, weight=1)
        _font = ("Microsoft JhengHei", 13)
        self._folder_var = tk.StringVar(value=self._cfg["output_folder"])
        ttk.Entry(f_folder, textvariable=self._folder_var,
                  state="readonly", width=38, font=_font).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(f_folder, text="變更", width=6,
                   command=self._change_folder).grid(row=0, column=1)

        # 快捷鍵
        f_hotkey = ttk.LabelFrame(tab, text=" 快捷鍵 ", padding=8)
        f_hotkey.pack(fill="x", pady=(0, 10))
        self._hotkey_var = tk.StringVar(value=self._cfg["hotkey"])
        self._hk_entry = ttk.Entry(f_hotkey, textvariable=self._hotkey_var,
                                   state="readonly", width=22, font=_font)
        self._hk_entry.pack(side="left")
        self._hk_entry.bind("<Button-1>", self._start_hotkey_capture)
        self._hk_hint_label = ttk.Label(f_hotkey, text="  ⓘ 點擊方框後按下新組合鍵",
                                        style="Hint.TLabel")
        self._hk_hint_label.pack(side="left")

        # 錄製設定
        f_rec = ttk.LabelFrame(tab, text=" 錄製設定 ", padding=8)
        f_rec.pack(fill="x", pady=(0, 10))

        row1 = ttk.Frame(f_rec)
        row1.pack(fill="x", pady=(0, 6))
        ttk.Label(row1, text="FPS：").pack(side="left")
        self._fps_var = tk.IntVar(value=self._cfg["fps"])
        for v in (5, 10, 15, 20):
            ttk.Radiobutton(row1, text=str(v), variable=self._fps_var,
                            value=v, command=self._save_settings).pack(side="left", padx=4)
        ttk.Label(row1, text="  自訂：").pack(side="left")
        ttk.Spinbox(row1, from_=1, to=60, width=5,
                    textvariable=self._fps_var, font=_font).pack(side="left")

        row2 = ttk.Frame(f_rec)
        row2.pack(fill="x", pady=(0, 6))
        ttk.Label(row2, text="縮放：").pack(side="left")
        self._scale_var = tk.DoubleVar(value=self._cfg["scale"])
        for label, val in (("100%", 1.0), ("75%", 0.75), ("50%", 0.5)):
            ttk.Radiobutton(row2, text=label, variable=self._scale_var,
                            value=val, command=self._save_settings).pack(side="left", padx=4)

        row3 = ttk.Frame(f_rec)
        row3.pack(fill="x")
        self._countdown_var = tk.BooleanVar(value=self._cfg["countdown"])
        ttk.Checkbutton(row3, text="開始前倒數 3 秒",
                        variable=self._countdown_var,
                        command=self._save_settings).pack(side="left")

        # 進階影像設定
        ttk.Button(tab, text="⚙  進階影像設定",
                   command=self._open_advanced).pack(pady=(6, 0))

        # 自動儲存 traces
        for var in (self._fps_var, self._scale_var):
            var.trace_add("write", lambda *_: self._save_settings())

    def _change_folder(self):
        folder = filedialog.askdirectory(initialdir=self._folder_var.get())
        if folder:
            self._folder_var.set(folder)
            self._save_settings()

    def _save_settings(self):
        try:
            cfg = config.load()
            cfg["output_folder"]    = self._folder_var.get()
            cfg["hotkey"]           = self._hotkey_var.get()
            cfg["record_mode"]      = self._mode_var.get()
            cfg["default_duration"] = int(self._duration_var.get())
            cfg["fps"]              = int(self._fps_var.get())
            cfg["scale"]            = float(self._scale_var.get())
            cfg["countdown"]        = bool(self._countdown_var.get())
            config.save(cfg)
            self._cfg = cfg
            self._hotkey_hint.config(
                text=f"按下 {cfg['hotkey'].upper()} 開始框選")
        except Exception:
            pass

    def _open_advanced(self):
        cfg = config.load()
        win = tk.Toplevel(self.root)
        win.title("進階影像設定")
        win.resizable(False, False)
        win.grab_set()

        pad = {"padx": 14, "pady": 6}

        # GIF
        f_gif = ttk.LabelFrame(win, text=" GIF ", padding=8)
        f_gif.pack(fill="x", **pad)
        colors_var = tk.IntVar(value=cfg["gif"]["colors"])
        dither_var = tk.BooleanVar(value=cfg["gif"]["dithering"])
        row = ttk.Frame(f_gif); row.pack(fill="x", pady=2)
        ttk.Label(row, text="色彩數：").pack(side="left")
        ttk.Combobox(row, textvariable=colors_var, width=6,
                     values=[2, 4, 8, 16, 32, 64, 128, 256],
                     state="readonly").pack(side="left")
        ttk.Checkbutton(f_gif, text="Dithering（建議開啟，提升漸層品質）",
                        variable=dither_var).pack(anchor="w")

        # MP4
        f_mp4 = ttk.LabelFrame(win, text=" MP4 ", padding=8)
        f_mp4.pack(fill="x", **pad)
        crf_presets = {"低（檔案大）": 18, "中（預設）": 23, "高（檔案小）": 28}
        crf_var = tk.IntVar(value=cfg["mp4"]["crf"])
        row2 = ttk.Frame(f_mp4); row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="品質：").pack(side="left")
        for label, val in crf_presets.items():
            ttk.Radiobutton(row2, text=label, variable=crf_var,
                            value=val).pack(side="left", padx=4)
        row3 = ttk.Frame(f_mp4); row3.pack(fill="x", pady=2)
        ttk.Label(row3, text="自訂 CRF（0-51）：").pack(side="left")
        ttk.Spinbox(row3, from_=0, to=51, width=5,
                    textvariable=crf_var).pack(side="left")

        def _apply():
            cfg["gif"]["colors"]    = int(colors_var.get())
            cfg["gif"]["dithering"] = bool(dither_var.get())
            cfg["mp4"]["crf"]       = int(crf_var.get())
            config.save(cfg)
            self._cfg = cfg
            win.destroy()

        btn_row = ttk.Frame(win)
        btn_row.pack(pady=(4, 12))
        ttk.Button(btn_row, text="確定", command=_apply, width=10).pack(
            side="left", padx=4, ipady=4)
        ttk.Button(btn_row, text="取消", command=win.destroy, width=10).pack(
            side="left", padx=4, ipady=4)

    # ---- 快捷鍵設定捕捉 ----

    def _start_hotkey_capture(self, _event=None):
        self._hk_entry.config(state="normal")
        self._hotkey_var.set("請按下組合鍵...")
        self._hk_hint_label.config(text="  按 Esc 取消")
        self._hk_entry.focus_set()
        self._hk_entry.bind("<KeyPress>", self._capture_hotkey_press)
        self._hk_entry.bind("<FocusOut>", self._cancel_hotkey_capture)

    def _cancel_hotkey_capture(self, _event=None):
        self._hk_entry.unbind("<KeyPress>")
        self._hk_entry.unbind("<FocusOut>")
        self._hotkey_var.set(self._cfg["hotkey"])
        self._hk_entry.config(state="readonly")
        self._hk_hint_label.config(text="  ⓘ 點擊方框後按下新組合鍵")

    def _capture_hotkey_press(self, event):
        if event.keysym == "Escape":
            self._cancel_hotkey_capture()
            return "break"
        parts = []
        if event.state & 0x4:   parts.append("ctrl")
        if event.state & 0x1:   parts.append("shift")
        if event.state & 0x8:   parts.append("alt")
        key = event.keysym.lower()
        if key in ("control_l", "control_r", "shift_l", "shift_r",
                   "alt_l", "alt_r", "super_l", "super_r"):
            return "break"
        if not parts:
            return "break"
        parts.append(key)
        new_hk = "+".join(parts)
        self._hk_entry.unbind("<KeyPress>")
        self._hk_entry.unbind("<FocusOut>")
        self._hotkey_var.set(new_hk)
        self._hk_entry.config(state="readonly")
        self._hk_hint_label.config(text="  ⓘ 點擊方框後按下新組合鍵")
        self._start_hotkey_listener(new_hk)
        self._save_settings()
        return "break"

    # ---- pynput 監聽 ----

    def _start_hotkey_listener(self, hotkey_str: str):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
        try:
            from pynput import keyboard
            parts = hotkey_str.split("+")
            pynput_str = "+".join(
                f"<{p}>" if len(p) > 1 else p for p in parts
            )

            def on_activate():
                self.root.after(0, self._trigger_recording)

            self._listener = keyboard.GlobalHotKeys({pynput_str: on_activate})
            self._listener.daemon = True
            self._listener.start()
        except Exception as e:
            print(f"[WARN] 快捷鍵監聽啟動失敗：{e}")

    # ================================================================
    # 主要工作 Tab（佔位，Task 7 填入）
    # ================================================================

    def _build_main_tab(self):
        tab = self._tab_main

        # 狀態
        f_status = ttk.LabelFrame(tab, text=" 狀態 ", padding=8)
        f_status.pack(fill="x", pady=(0, 8))
        self._status_label = ttk.Label(f_status, text="● 就緒", foreground="#27ae60")
        self._status_label.pack(anchor="w")
        self._hotkey_hint = ttk.Label(
            f_status,
            text=f"按下 {self._cfg['hotkey'].upper()} 開始框選",
            style="Hint.TLabel",
        )
        self._hotkey_hint.pack(anchor="w")

        # 輸出格式
        f_fmt = ttk.LabelFrame(tab, text=" 輸出格式 ", padding=8)
        f_fmt.pack(fill="x", pady=(0, 8))
        self._format_var = tk.StringVar(value="both")
        for text, val in (("GIF", "gif"), ("MP4", "mp4"), ("GIF + MP4", "both")):
            ttk.Radiobutton(f_fmt, text=text, variable=self._format_var,
                            value=val).pack(side="left", padx=8)

        # 錄製模式
        f_mode = ttk.LabelFrame(tab, text=" 錄製模式 ", padding=8)
        f_mode.pack(fill="x", pady=(0, 8))
        self._mode_var = tk.StringVar(value=self._cfg.get("record_mode", "fixed"))
        _font = ("Microsoft JhengHei", 13)
        self._duration_var = tk.IntVar(value=self._cfg["default_duration"])

        row_fixed = ttk.Frame(f_mode)
        row_fixed.pack(fill="x", pady=(0, 4))
        ttk.Radiobutton(row_fixed, text="固定秒數：", variable=self._mode_var,
                        value="fixed", command=self._on_mode_change).pack(side="left")
        self._duration_spinbox = ttk.Spinbox(
            row_fixed, from_=1, to=300, width=6,
            textvariable=self._duration_var, font=_font)
        self._duration_spinbox.pack(side="left")
        ttk.Label(row_fixed, text=" 秒").pack(side="left")

        ttk.Radiobutton(f_mode, text="手動停止（再按快捷鍵停止）",
                        variable=self._mode_var,
                        value="manual", command=self._on_mode_change).pack(anchor="w")

        self._on_mode_change()  # 初始化 spinbox 狀態
        self._duration_var.trace_add("write", lambda *_: self._save_settings())

        # 錄製進度（隱藏）
        self._f_progress = ttk.LabelFrame(tab, text=" 錄製進度 ", padding=8)
        self._progress_bar = ttk.Progressbar(
            self._f_progress, mode="determinate", length=280)
        self._progress_bar.pack(fill="x")
        self._progress_label = ttk.Label(self._f_progress, text="0.0 / 0 秒")
        self._progress_label.pack(anchor="w", pady=(4, 0))
        btn_row = ttk.Frame(self._f_progress)
        btn_row.pack(pady=(6, 0))
        self._btn_stop = ttk.Button(
            btn_row, text="⏹  提早停止", command=self._stop_recording)
        self._btn_stop.pack(side="left", padx=(0, 8), ipady=4)
        self._btn_discard = ttk.Button(
            btn_row, text="🗑  廢棄", command=self._discard_recording)
        self._btn_discard.pack(side="left", ipady=4)

        # 最後輸出（隱藏）
        self._f_output = ttk.LabelFrame(tab, text=" 最後輸出 ", padding=8)
        self._output_labels: list = []
        self._btn_open_folder = ttk.Button(
            self._f_output, text="📂  開啟資料夾",
            command=self._open_output_folder)
        self._btn_open_folder.pack(pady=(4, 0))

        self._last_output_folder = ""

    def _build_editor_tab(self):
        try:
            from src.editor import EditorTab
            EditorTab(self._tab_editor, self._cfg)
        except (ImportError, AttributeError):
            ttk.Label(self._tab_editor, text="影像編輯 Tab（Task 8 實作）").pack()

    # ---- 觸發錄製 ----

    def _trigger_recording(self):
        if self._recorder is not None:
            return  # 已在錄製中
        cfg = config.load()
        from src.overlay import FullscreenOverlay
        FullscreenOverlay(
            self.root,
            countdown=cfg["countdown"],
            on_complete=self._on_region_selected,
        )

    def _on_region_selected(self, x1: int, y1: int, x2: int, y2: int):
        cfg = config.load()
        region = {"top": y1, "left": x1, "width": x2 - x1, "height": y2 - y1}
        mode = self._mode_var.get()
        duration = int(self._duration_var.get()) if mode == "fixed" else 0

        from src.overlay import RecordingBorder
        self._border = RecordingBorder(self.root, x1, y1, x2, y2)

        # 顯示進度區
        self._f_progress.pack(fill="x", pady=(0, 8))
        self._f_output.pack_forget()
        if mode == "fixed":
            self._progress_bar.config(mode="determinate", maximum=duration)
            self._progress_bar["value"] = 0
            self._progress_label.config(text=f"0.0 / {duration} 秒")
        else:
            self._progress_bar.config(mode="indeterminate", maximum=100)
            self._progress_bar.start(50)
            self._progress_label.config(text="錄製中... 按快捷鍵停止")
        self._recording_mode = mode
        self._status_label.config(text="● 錄製中...", foreground="#e74c3c")

        from src.recorder import Recorder
        self._recorder = Recorder(
            region=region,
            fps=cfg["fps"],
            scale=cfg["scale"],
            duration=duration,
            output_folder=cfg["output_folder"],
            output_format=self._format_var.get(),
            gif_colors=cfg["gif"]["colors"],
            gif_dither=cfg["gif"]["dithering"],
            mp4_crf=cfg["mp4"]["crf"],
            on_progress=lambda e: self.msg_queue.put(("progress", e)),
            on_done=lambda paths, err: self.msg_queue.put(("done", (paths, err))),
        )
        self._recorder.start()
        self._start_hotkey_listener_stop_mode()

    def _on_mode_change(self):
        if self._mode_var.get() == "fixed":
            self._duration_spinbox.config(state="normal")
        else:
            self._duration_spinbox.config(state="disabled")
        self._save_settings()

    def _stop_recording(self):
        if self._recorder:
            self._recorder.stop()

    def _discard_recording(self):
        if self._recorder:
            self._recorder.discard()

    def _start_hotkey_listener_stop_mode(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
        try:
            from pynput import keyboard
            cfg = config.load()
            parts = cfg["hotkey"].split("+")
            pynput_str = "+".join(f"<{p}>" if len(p) > 1 else p for p in parts)

            def on_stop():
                self.root.after(0, self._stop_recording)

            self._listener = keyboard.GlobalHotKeys({pynput_str: on_stop})
            self._listener.daemon = True
            self._listener.start()
        except Exception:
            pass

    def _open_output_folder(self):
        if self._last_output_folder and os.path.exists(self._last_output_folder):
            os.startfile(self._last_output_folder)

    # ---- Queue poll ----

    def _poll_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                self._handle_msg(msg_type, data)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _handle_msg(self, msg_type: str, data):
        cfg = config.load()
        if msg_type == "progress":
            elapsed = data
            if getattr(self, "_recording_mode", "fixed") == "fixed":
                duration = int(self._duration_var.get())
                self._progress_bar["value"] = min(elapsed, duration)
                self._progress_label.config(text=f"{elapsed:.1f} / {duration} 秒")
            else:
                self._progress_label.config(text=f"錄製中... {elapsed:.1f} 秒")
        elif msg_type == "done":
            paths, error = data
            self._progress_bar.stop()
            if self._border:
                self._border.destroy()
                self._border = None
            self._recorder = None
            self._f_progress.pack_forget()
            self._start_hotkey_listener(cfg["hotkey"])

            if error:
                self._status_label.config(text=f"❌ 錯誤：{error}", foreground="#e74c3c")
                return

            # 廢棄：paths 為空且無 error，靜默重置
            if not paths:
                self._status_label.config(text="● 就緒", foreground="#27ae60")
                self._hotkey_hint.config(text=f"按下 {cfg['hotkey'].upper()} 開始框選")
                return

            for lbl in self._output_labels:
                lbl.destroy()
            self._output_labels.clear()
            for p in paths:
                lbl = ttk.Label(self._f_output, text=f"📄 {os.path.basename(p)}",
                                foreground="#2980b9")
                lbl.pack(anchor="w")
                self._output_labels.append(lbl)
            self._last_output_folder = os.path.dirname(paths[0]) if paths else ""
            self._f_output.pack(fill="x", pady=(0, 8))
            self._status_label.config(text="● 就緒", foreground="#27ae60")
            self._hotkey_hint.config(text=f"按下 {cfg['hotkey'].upper()} 開始框選")


def main():
    show_cth_banner()
    root = tk.Tk()
    SnapGIFClipApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
