# SnapGIFClip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 SnapGIFClip — 一個 Windows tkinter 工具，按下快捷鍵後框選螢幕區域，錄製成 GIF/MP4；附帶影像編輯 tab 可載入任意 GIF/MP4 做裁切與調速。

**Architecture:** 主視窗 3 個 Tab（主要工作 / 影像編輯 / 設定），`pynput` 監聽 App 內快捷鍵；`overlay.py` 管理選框暗幕與錄製紅框；`recorder.py` 以 `mss` 擷幀、`Pillow`/`imageio` 輸出 GIF、本地 `bin/ffmpeg.exe` 輸出 MP4；`editor.py` 處理影像編輯 Tab 所有邏輯。

**Tech Stack:** Python 3.10+, tkinter + sv-ttk, mss, Pillow, imageio, pynput, ffmpeg（本地 bin/）

---

## 檔案清單

| 路徑 | 角色 |
|------|------|
| `SnapGIFClip啟動器.bat` | 唯一入口（薄殼，2 行） |
| `launcher.ps1` | 環境檢查、ffmpeg 下載、venv 建立、啟動 |
| `requirements.txt` | Python 套件清單 |
| `src/main.py` | 主視窗、3 Tab、hotkey 監聽、queue 通訊 |
| `src/overlay.py` | FullscreenOverlay（選框）、RecordingBorder（紅框） |
| `src/recorder.py` | mss 截圖迴圈、GIF/MP4 編碼 |
| `src/editor.py` | 影像編輯 Tab：載入、預覽、裁切、調速、估算、匯出 |
| `src/config.py` | 讀寫 src/config.json |
| `src/config.json` | 使用者設定（自動生成） |
| `tests/test_config.py` | config 單元測試 |
| `tests/test_recorder.py` | 編碼邏輯單元測試 |
| `tests/test_editor.py` | 裁切/調速/估算邏輯單元測試 |

---

## Task 1：專案鷹架

**Files:**
- Create: `SnapGIFClip啟動器.bat`
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `bin/.gitkeep`

- [ ] **Step 1：建立目錄結構**

```powershell
$base = "C:\Users\CTH\Documents\Code\Snap GIF Creator"
New-Item -ItemType Directory -Force "$base\src"
New-Item -ItemType Directory -Force "$base\bin"
New-Item -ItemType Directory -Force "$base\tests"
New-Item -ItemType File -Force "$base\src\__init__.py"
New-Item -ItemType File -Force "$base\tests\__init__.py"
New-Item -ItemType File -Force "$base\bin\.gitkeep"
```

- [ ] **Step 2：建立 `.gitignore`**

```
venv/
__pycache__/
*.pyc
*.pyo
.env
*.log
cache/
bin/ffmpeg.exe
src/config.json
```

- [ ] **Step 3：建立 `requirements.txt`**

```
mss
Pillow
imageio
pynput
sv-ttk
```

- [ ] **Step 4：建立 `SnapGIFClip啟動器.bat`（2 行，不可修改）**

```bat
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher.ps1"
```

- [ ] **Step 5：Commit**

```bash
git init
git add .gitignore requirements.txt "SnapGIFClip啟動器.bat" src/ tests/ bin/
git commit -m "chore: project scaffold"
```

---

## Task 2：config.py

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1：建立 `tests/test_config.py`**

```python
import json
import os
import tempfile
import pytest

# 暫時替換 CONFIG_PATH 再 import
os.environ["SNAPGIFCLIP_CONFIG"] = ""

def test_load_defaults_when_missing(tmp_path, monkeypatch):
    cfg_path = str(tmp_path / "config.json")
    monkeypatch.setenv("SNAPGIFCLIP_CONFIG", cfg_path)
    import importlib, src.config as c
    importlib.reload(c)
    result = c.load()
    assert result["fps"] == 15
    assert result["scale"] == 1.0
    assert result["countdown"] is True
    assert result["gif"]["colors"] == 256

def test_save_and_reload(tmp_path, monkeypatch):
    cfg_path = str(tmp_path / "config.json")
    monkeypatch.setenv("SNAPGIFCLIP_CONFIG", cfg_path)
    import importlib, src.config as c
    importlib.reload(c)
    c.save({"fps": 10, "scale": 0.5, "countdown": False,
            "gif": {"colors": 128, "dithering": False},
            "mp4": {"crf": 28},
            "output_folder": "C:\\test",
            "hotkey": "ctrl+shift+g",
            "default_duration": 5})
    result = c.load()
    assert result["fps"] == 10
    assert result["gif"]["colors"] == 128

def test_load_merges_missing_keys(tmp_path, monkeypatch):
    cfg_path = str(tmp_path / "config.json")
    with open(cfg_path, "w") as f:
        json.dump({"fps": 20}, f)
    monkeypatch.setenv("SNAPGIFCLIP_CONFIG", cfg_path)
    import importlib, src.config as c
    importlib.reload(c)
    result = c.load()
    assert result["fps"] == 20
    assert result["scale"] == 1.0   # default 補上
```

- [ ] **Step 2：執行確認失敗**

```bash
cd "C:\Users\CTH\Documents\Code\Snap GIF Creator"
venv\Scripts\python -m pytest tests/test_config.py -v
```

預期：`ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3：建立 `src/config.py`**

```python
"""SnapGIFClip 設定讀寫模組。"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("SNAPGIFCLIP_CONFIG") or os.path.join(SCRIPT_DIR, "config.json")

DEFAULT = {
    "output_folder": os.path.join(os.path.expanduser("~"), "Desktop"),
    "hotkey": "ctrl+shift+g",
    "default_duration": 10,
    "fps": 15,
    "scale": 1.0,
    "countdown": True,
    "gif": {"colors": 256, "dithering": True},
    "mp4": {"crf": 23},
}


def load() -> dict:
    path = os.environ.get("SNAPGIFCLIP_CONFIG") or os.path.join(SCRIPT_DIR, "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        merged = dict(DEFAULT)
        merged.update(raw)
        merged["gif"] = {**DEFAULT["gif"], **raw.get("gif", {})}
        merged["mp4"] = {**DEFAULT["mp4"], **raw.get("mp4", {})}
        return merged
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT)


def save(cfg: dict):
    path = os.environ.get("SNAPGIFCLIP_CONFIG") or os.path.join(SCRIPT_DIR, "config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def update(**kwargs):
    cfg = load()
    cfg.update(kwargs)
    save(cfg)
```

- [ ] **Step 4：執行確認通過**

```bash
venv\Scripts\python -m pytest tests/test_config.py -v
```

預期：3 個測試全部 PASS

- [ ] **Step 5：Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add config read/write module"
```

---

## Task 3：recorder.py — GIF/MP4 編碼邏輯

**Files:**
- Create: `src/recorder.py`
- Create: `tests/test_recorder.py`

- [ ] **Step 1：建立 `tests/test_recorder.py`**

```python
import os
import sys
import tempfile
from PIL import Image
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.recorder import encode_gif, encode_mp4

FFMPEG = os.path.join(os.path.dirname(__file__), "..", "bin", "ffmpeg.exe")

def make_frames(count=5, size=(64, 64)):
    """產生測試用純色 frames（紅→綠漸變）"""
    frames = []
    for i in range(count):
        r = int(255 * i / (count - 1))
        g = 255 - r
        img = Image.new("RGB", size, (r, g, 0))
        frames.append(img)
    return frames


def test_encode_gif_creates_file(tmp_path):
    frames = make_frames()
    out = str(tmp_path / "test.gif")
    encode_gif(frames, out, fps=10, colors=256, dithering=True)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0


def test_encode_gif_frame_count(tmp_path):
    frames = make_frames(8)
    out = str(tmp_path / "test.gif")
    encode_gif(frames, out, fps=10, colors=256, dithering=True)
    with Image.open(out) as gif:
        count = 0
        try:
            while True:
                count += 1
                gif.seek(gif.tell() + 1)
        except EOFError:
            pass
    assert count == 8


@pytest.mark.skipif(not os.path.exists(FFMPEG), reason="ffmpeg not installed")
def test_encode_mp4_creates_file(tmp_path):
    frames = make_frames()
    out = str(tmp_path / "test.mp4")
    encode_mp4(frames, out, fps=10, crf=28, ffmpeg_path=FFMPEG)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0
```

- [ ] **Step 2：執行確認失敗**

```bash
venv\Scripts\python -m pytest tests/test_recorder.py -v
```

預期：`ImportError: cannot import name 'encode_gif'`

- [ ] **Step 3：建立 `src/recorder.py`**

```python
"""SnapGIFClip 截圖擷幀與 GIF/MP4 編碼模組。"""
import os
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime

from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(SCRIPT_DIR, "..", "bin")
DEFAULT_FFMPEG = os.path.join(BIN_DIR, "ffmpeg.exe")


# ---- 純編碼函式（可獨立測試） ----

def encode_gif(frames: list, output_path: str, fps: int,
               colors: int, dithering: bool):
    """給定 PIL Image 列表，輸出 GIF 到 output_path。"""
    duration_ms = int(1000 / fps)
    dither_mode = Image.Dither.FLOYDSTEINBERG if dithering else Image.Dither.NONE
    converted = [
        f.convert("P", palette=Image.Palette.ADAPTIVE,
                  colors=colors, dither=dither_mode)
        for f in frames
    ]
    converted[0].save(
        output_path,
        save_all=True,
        append_images=converted[1:],
        loop=0,
        duration=duration_ms,
        optimize=True,
    )


def encode_mp4(frames: list, output_path: str, fps: int,
               crf: int, ffmpeg_path: str = DEFAULT_FFMPEG):
    """給定 PIL Image 列表，輸出 MP4 到 output_path（需要 ffmpeg）。"""
    tmp_dir = tempfile.mkdtemp()
    try:
        for i, frame in enumerate(frames):
            frame.save(os.path.join(tmp_dir, f"frame_{i:06d}.png"))
        cmd = [
            ffmpeg_path, "-y",
            "-framerate", str(fps),
            "-i", os.path.join(tmp_dir, "frame_%06d.png"),
            "-c:v", "libx264",
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg 錯誤：{result.stderr[-500:]}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---- 擷幀錄製器 ----

class Recorder:
    """
    背景執行緒錄製器。
    呼叫 start() 開始；呼叫 stop() 或等待 duration 秒後自動停止；
    完成後透過 on_done(paths, error) 回呼。
    """

    def __init__(self, region: dict, fps: int, scale: float,
                 duration: int, output_folder: str, output_format: str,
                 gif_colors: int, gif_dither: bool, mp4_crf: int,
                 on_progress=None, on_done=None,
                 ffmpeg_path: str = DEFAULT_FFMPEG):
        """
        region: {"top": y1, "left": x1, "width": w, "height": h}
        output_format: "gif" | "mp4" | "both"
        on_progress: callback(elapsed_secs: float)
        on_done: callback(paths: list[str], error: str | None)
        """
        self.region = region
        self.fps = fps
        self.scale = scale
        self.duration = duration
        self.output_folder = output_folder
        self.output_format = output_format
        self.gif_colors = gif_colors
        self.gif_dither = gif_dither
        self.mp4_crf = mp4_crf
        self.on_progress = on_progress
        self.on_done = on_done
        self.ffmpeg_path = ffmpeg_path
        self._stop_event = threading.Event()

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        import mss
        frames = []
        interval = 1.0 / self.fps
        start_time = time.time()

        with mss.mss() as sct:
            while not self._stop_event.is_set():
                elapsed = time.time() - start_time
                if elapsed >= self.duration:
                    break
                frame_start = time.time()
                raw = sct.grab(self.region)
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                if self.scale != 1.0:
                    nw = max(2, int(img.width * self.scale))
                    nh = max(2, int(img.height * self.scale))
                    img = img.resize((nw, nh), Image.LANCZOS)
                frames.append(img)
                if self.on_progress:
                    self.on_progress(elapsed)
                sleep = interval - (time.time() - frame_start)
                if sleep > 0:
                    time.sleep(sleep)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        paths, error = [], None
        try:
            os.makedirs(self.output_folder, exist_ok=True)
            if self.output_format in ("gif", "both"):
                p = os.path.join(self.output_folder, f"snap_{timestamp}.gif")
                encode_gif(frames, p, self.fps, self.gif_colors, self.gif_dither)
                paths.append(p)
            if self.output_format in ("mp4", "both"):
                p = os.path.join(self.output_folder, f"snap_{timestamp}.mp4")
                encode_mp4(frames, p, self.fps, self.mp4_crf, self.ffmpeg_path)
                paths.append(p)
        except Exception as e:
            error = str(e)

        if self.on_done:
            self.on_done(paths, error)
```

- [ ] **Step 4：執行確認通過**

```bash
venv\Scripts\python -m pytest tests/test_recorder.py -v
```

預期：`test_encode_gif_creates_file` PASS，`test_encode_gif_frame_count` PASS，`test_encode_mp4_creates_file` SKIP（ffmpeg 尚未安裝）

- [ ] **Step 5：Commit**

```bash
git add src/recorder.py tests/test_recorder.py
git commit -m "feat: add GIF/MP4 encoding and Recorder class"
```

---

## Task 4：overlay.py — 選框暗幕與錄製紅框

**Files:**
- Create: `src/overlay.py`

（此模組需要螢幕顯示，不寫自動化測試；靠 Task 8 整合測試驗證）

- [ ] **Step 1：建立 `src/overlay.py`**

```python
"""SnapGIFClip overlay 模組：選框暗幕 + 錄製紅框。"""
import tkinter as tk


class FullscreenOverlay:
    """
    全螢幕半透明暗幕，讓使用者拖拉選取錄製區域。
    完成後呼叫 on_complete(x1, y1, x2, y2)；Esc 取消則不呼叫。
    若 countdown=True，選取後先顯示 3-2-1 再呼叫 on_complete。
    """

    def __init__(self, root: tk.Tk, countdown: bool = False, on_complete=None):
        self._root = root
        self._countdown = countdown
        self._on_complete = on_complete
        self._sx = self._sy = 0
        self._rect_id = None

        self._win = tk.Toplevel(root)
        self._win.attributes("-fullscreen", True)
        self._win.attributes("-alpha", 0.35)
        self._win.attributes("-topmost", True)
        self._win.configure(bg="black", cursor="crosshair")

        self._canvas = tk.Canvas(
            self._win, bg="black", highlightthickness=0, cursor="crosshair"
        )
        self._canvas.pack(fill="both", expand=True)

        sw = self._win.winfo_screenwidth()
        self._canvas.create_text(
            sw // 2, 36,
            text="拖拉選取錄製區域　　Esc 取消",
            fill="white",
            font=("Microsoft JhengHei", 16),
        )

        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._win.bind("<Escape>", lambda _: self._win.destroy())

    def _on_press(self, event):
        self._sx, self._sy = event.x, event.y
        if self._rect_id:
            self._canvas.delete(self._rect_id)

    def _on_drag(self, event):
        if self._rect_id:
            self._canvas.delete(self._rect_id)
        self._rect_id = self._canvas.create_rectangle(
            self._sx, self._sy, event.x, event.y,
            outline="white", width=2,
        )

    def _on_release(self, event):
        x1, y1 = min(self._sx, event.x), min(self._sy, event.y)
        x2, y2 = max(self._sx, event.x), max(self._sy, event.y)
        if x2 - x1 < 10 or y2 - y1 < 10:
            return
        self._win.destroy()
        if self._countdown:
            self._show_countdown(x1, y1, x2, y2)
        elif self._on_complete:
            self._on_complete(x1, y1, x2, y2)

    def _show_countdown(self, x1, y1, x2, y2):
        win = tk.Toplevel(self._root)
        win.attributes("-fullscreen", True)
        win.attributes("-alpha", 0.4)
        win.attributes("-topmost", True)
        win.configure(bg="black")
        canvas = tk.Canvas(win, bg="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        label_id = canvas.create_text(
            sw // 2, sh // 2, text="3",
            fill="white", font=("Microsoft JhengHei", 120, "bold"),
        )
        count = [3]

        def tick():
            if count[0] > 0:
                canvas.itemconfig(label_id, text=str(count[0]))
                count[0] -= 1
                win.after(1000, tick)
            else:
                win.destroy()
                if self._on_complete:
                    self._on_complete(x1, y1, x2, y2)

        tick()


class RecordingBorder:
    """
    在選取區域四周顯示紅色邊框，錄製期間常駐。
    使用 4 個細長 Toplevel 視窗實現，避免透明色問題。
    """
    THICKNESS = 3

    def __init__(self, root: tk.Tk, x1: int, y1: int, x2: int, y2: int):
        B = self.THICKNESS
        W, H = x2 - x1, y2 - y1
        self._wins: list[tk.Toplevel] = []
        # top / bottom / left / right
        specs = [
            (x1,     y1 - B, W,         B    ),
            (x1,     y2,     W,         B    ),
            (x1 - B, y1 - B, B,         H + B * 2),
            (x2,     y1 - B, B,         H + B * 2),
        ]
        for (bx, by, bw, bh) in specs:
            w = tk.Toplevel(root)
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            w.geometry(f"{bw}x{bh}+{bx}+{by}")
            w.configure(bg="red")
            self._wins.append(w)

    def destroy(self):
        for w in self._wins:
            try:
                w.destroy()
            except tk.TclError:
                pass
        self._wins.clear()
```

- [ ] **Step 2：Commit**

```bash
git add src/overlay.py
git commit -m "feat: add fullscreen selection overlay and recording border"
```

---

## Task 5：editor.py — 裁切/調速/估算邏輯

先實作純計算邏輯（無 UI），讓測試可以驗證。

**Files:**
- Create: `src/editor.py`（純邏輯部分）
- Create: `tests/test_editor.py`

- [ ] **Step 1：建立 `tests/test_editor.py`**

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.editor import calc_output_duration, estimate_gif_size, estimate_mp4_size


def test_calc_output_duration_basic():
    assert calc_output_duration(start=2.0, end=8.0, speed=1.0) == pytest.approx(6.0)


def test_calc_output_duration_speed():
    # 6 秒 @ 0.5x 播放 → 輸出 12 秒（播慢）
    assert calc_output_duration(start=2.0, end=8.0, speed=0.5) == pytest.approx(12.0)


def test_calc_output_duration_fast():
    # 6 秒 @ 2x 播放 → 輸出 3 秒
    assert calc_output_duration(start=2.0, end=8.0, speed=2.0) == pytest.approx(3.0)


def test_estimate_gif_size_reasonable():
    # 640x360, 10fps, 5 秒, 256 色 → 預期 1~20 MB
    size_mb = estimate_gif_size(width=640, height=360, fps=10,
                                duration_secs=5.0, colors=256)
    assert 0.5 < size_mb < 30.0


def test_estimate_mp4_size_reasonable():
    # 640x360, 10fps, 5 秒, CRF 23
    size_mb = estimate_mp4_size(width=640, height=360, fps=10,
                                duration_secs=5.0, crf=23)
    assert 0.1 < size_mb < 10.0


import pytest
```

- [ ] **Step 2：執行確認失敗**

```bash
venv\Scripts\python -m pytest tests/test_editor.py -v
```

預期：`ImportError: cannot import name 'calc_output_duration'`

- [ ] **Step 3：在 `src/editor.py` 建立純邏輯函式（UI 部分後續 Task 加入）**

```python
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
```

- [ ] **Step 4：執行確認通過**

```bash
venv\Scripts\python -m pytest tests/test_editor.py -v
```

預期：5 個測試全部 PASS

- [ ] **Step 5：Commit**

```bash
git add src/editor.py tests/test_editor.py
git commit -m "feat: add editor calculation functions with tests"
```

---

## Task 6：main.py — 視窗骨架 + 設定 Tab

**Files:**
- Create: `src/main.py`

- [ ] **Step 1：建立 `src/main.py`（視窗骨架 + 設定 Tab）**

```python
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
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

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

        self._apply_font()
        self._build_ui()
        self._start_hotkey_listener(self._cfg["hotkey"])
        self._poll_queue()

    # ---- 字型 ----

    def _apply_font(self):
        from tkinter import font as tkfont
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
            try:
                tkfont.nametofont(name).configure(family="Microsoft JhengHei", size=11)
            except Exception:
                pass

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
        self._folder_var = tk.StringVar(value=self._cfg["output_folder"])
        ttk.Entry(f_folder, textvariable=self._folder_var,
                  state="readonly", width=38).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(f_folder, text="變更", width=6,
                   command=self._change_folder).grid(row=0, column=1)

        # 快捷鍵
        f_hotkey = ttk.LabelFrame(tab, text=" 快捷鍵 ", padding=8)
        f_hotkey.pack(fill="x", pady=(0, 10))
        self._hotkey_var = tk.StringVar(value=self._cfg["hotkey"])
        hk_entry = ttk.Entry(f_hotkey, textvariable=self._hotkey_var,
                             state="readonly", width=22)
        hk_entry.pack(side="left")
        hk_entry.bind("<Button-1>", self._start_hotkey_capture)
        ttk.Label(f_hotkey, text="  ⓘ 點擊方框後按下新組合鍵",
                  foreground="gray").pack(side="left")

        # 錄製設定
        f_rec = ttk.LabelFrame(tab, text=" 錄製設定 ", padding=8)
        f_rec.pack(fill="x", pady=(0, 10))

        row0 = ttk.Frame(f_rec)
        row0.pack(fill="x", pady=(0, 6))
        ttk.Label(row0, text="預設秒數：").pack(side="left")
        self._duration_var = tk.IntVar(value=self._cfg["default_duration"])
        ttk.Spinbox(row0, from_=1, to=300, width=6,
                    textvariable=self._duration_var).pack(side="left")
        ttk.Label(row0, text=" 秒").pack(side="left")

        row1 = ttk.Frame(f_rec)
        row1.pack(fill="x", pady=(0, 6))
        ttk.Label(row1, text="FPS：").pack(side="left")
        self._fps_var = tk.IntVar(value=self._cfg["fps"])
        for v in (5, 10, 15, 20):
            ttk.Radiobutton(row1, text=str(v), variable=self._fps_var,
                            value=v, command=self._save_settings).pack(side="left", padx=4)
        ttk.Label(row1, text="  自訂：").pack(side="left")
        ttk.Spinbox(row1, from_=1, to=60, width=5,
                    textvariable=self._fps_var).pack(side="left")

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
        for var in (self._duration_var, self._fps_var, self._scale_var):
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
            cfg["default_duration"] = int(self._duration_var.get())
            cfg["fps"]              = int(self._fps_var.get())
            cfg["scale"]            = float(self._scale_var.get())
            cfg["countdown"]        = bool(self._countdown_var.get())
            config.save(cfg)
            self._cfg = cfg
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
        self._hotkey_var.set("請按下新快捷鍵...")
        self.root.bind("<KeyPress>", self._capture_hotkey_press)

    def _capture_hotkey_press(self, event):
        self.root.unbind("<KeyPress>")
        parts = []
        if event.state & 0x4:  parts.append("ctrl")
        if event.state & 0x1:  parts.append("shift")
        if event.state & 0x20000: parts.append("alt")
        key = event.keysym.lower()
        if key not in ("control_l", "control_r", "shift_l", "shift_r",
                       "alt_l", "alt_r"):
            parts.append(key)
        if len(parts) >= 2:
            new_hk = "+".join(parts)
            self._hotkey_var.set(new_hk)
            self._start_hotkey_listener(new_hk)
            self._save_settings()
        else:
            self._hotkey_var.set(self._cfg["hotkey"])

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
        ttk.Label(self._tab_main,
                  text="主要工作 Tab（Task 7 實作）").pack()

    def _build_editor_tab(self):
        from src.editor import EditorTab
        EditorTab(self._tab_editor, self._cfg)

    # ---- 觸發錄製（Task 7 實作）----

    def _trigger_recording(self):
        pass

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
        pass  # Task 7 實作


def main():
    show_cth_banner()
    root = tk.Tk()
    SnapGIFClipApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2：執行程式確認視窗開啟正常**

```bash
venv\Scripts\python src\main.py
```

預期：視窗出現，有三個 Tab（主要工作 / 影像編輯 / 設定），設定 Tab 有完整控制項，進階影像設定按鈕可點開彈窗。

- [ ] **Step 3：Commit**

```bash
git add src/main.py
git commit -m "feat: main window skeleton with settings tab"
```

---

## Task 7：main.py — 主要工作 Tab + 錄製流程

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1：替換 `_build_main_tab` 方法**

在 `src/main.py` 中，找到 `def _build_main_tab(self):` 並替換整個方法：

```python
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
        foreground="gray", font=("Microsoft JhengHei", 9),
    )
    self._hotkey_hint.pack(anchor="w")

    # 輸出格式
    f_fmt = ttk.LabelFrame(tab, text=" 輸出格式 ", padding=8)
    f_fmt.pack(fill="x", pady=(0, 8))
    self._format_var = tk.StringVar(value="both")
    for text, val in (("GIF", "gif"), ("MP4", "mp4"), ("GIF + MP4", "both")):
        ttk.Radiobutton(f_fmt, text=text, variable=self._format_var,
                        value=val).pack(side="left", padx=8)

    # 錄製進度（隱藏）
    self._f_progress = ttk.LabelFrame(tab, text=" 錄製進度 ", padding=8)
    self._progress_bar = ttk.Progressbar(
        self._f_progress, mode="determinate", length=280)
    self._progress_bar.pack(fill="x")
    self._progress_label = ttk.Label(self._f_progress, text="0.0 / 0 秒")
    self._progress_label.pack(anchor="w", pady=(4, 0))
    self._btn_stop = ttk.Button(
        self._f_progress, text="⏹  提早停止", command=self._stop_recording)
    self._btn_stop.pack(pady=(6, 0), ipady=4)

    # 最後輸出（隱藏）
    self._f_output = ttk.LabelFrame(tab, text=" 最後輸出 ", padding=8)
    self._output_labels: list[ttk.Label] = []
    self._btn_open_folder = ttk.Button(
        self._f_output, text="📂  開啟資料夾",
        command=self._open_output_folder)
    self._btn_open_folder.pack(pady=(4, 0))

    self._last_output_folder = ""
```

- [ ] **Step 2：替換 `_trigger_recording` 與新增相關方法**

在 `_trigger_recording` 後加入以下方法（在 `_poll_queue` 之前插入）：

```python
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
    duration = cfg["default_duration"]

    from src.overlay import RecordingBorder
    self._border = RecordingBorder(self.root, x1, y1, x2, y2)

    # 顯示進度區
    self._f_progress.pack(fill="x", pady=(0, 8))
    self._f_output.pack_forget()
    self._progress_bar["maximum"] = duration
    self._progress_bar["value"] = 0
    self._progress_label.config(text=f"0.0 / {duration} 秒")
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
    # 快捷鍵二次按下 = 提早停止
    self._start_hotkey_listener_stop_mode()

def _stop_recording(self):
    if self._recorder:
        self._recorder.stop()

def _start_hotkey_listener_stop_mode(self):
    """錄製中，再按一次快捷鍵 = 停止。"""
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
```

- [ ] **Step 3：替換 `_handle_msg` 方法**

```python
def _handle_msg(self, msg_type: str, data):
    cfg = config.load()
    if msg_type == "progress":
        elapsed = data
        duration = cfg["default_duration"]
        self._progress_bar["value"] = min(elapsed, duration)
        self._progress_label.config(
            text=f"{elapsed:.1f} / {duration} 秒"
        )
    elif msg_type == "done":
        paths, error = data
        # 清除紅框
        if self._border:
            self._border.destroy()
            self._border = None
        self._recorder = None
        self._f_progress.pack_forget()
        # 恢復正常快捷鍵模式
        self._start_hotkey_listener(cfg["hotkey"])

        if error:
            self._status_label.config(text=f"❌ 錯誤：{error}", foreground="#e74c3c")
            return

        # 顯示輸出
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
```

- [ ] **Step 4：執行並手動測試錄製流程**

```bash
venv\Scripts\python src\main.py
```

測試步驟：
1. 切到設定 Tab，確認快捷鍵顯示正確
2. 回主要工作 Tab，按下快捷鍵 → 確認暗幕出現
3. 拖拉選取一個區域 → 確認紅框出現
4. 等待倒數結束 → 確認進度條開始動
5. 等預設秒數到 → 確認紅框消失、輸出區出現

- [ ] **Step 5：Commit**

```bash
git add src/main.py
git commit -m "feat: main tab and full recording flow"
```

---

## Task 8：editor.py — EditorTab UI

**Files:**
- Modify: `src/editor.py`（加入 EditorTab class）

- [ ] **Step 1：在 `src/editor.py` 末尾加入 `EditorTab` class**

```python
# ---- EditorTab UI ----

class EditorTab:
    """影像編輯 Tab 的完整 UI 與邏輯。"""

    PREVIEW_W = 460
    PREVIEW_H = 260

    def __init__(self, parent: tk.Widget, cfg: dict):
        self._parent = parent
        self._cfg = cfg
        self._frames: list[Image.Image] = []   # 原始解幀後的 PIL 列表
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
        ffmpeg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "ffmpeg.exe")
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
        img = self._frames[idx]
        # 縮放到 canvas 尺寸
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
        # 跳到 start frame 預覽
        self._show_frame(self._get_start_frame_idx())
        # debounce 估算
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
        ffmpeg = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "bin", "ffmpeg.exe"
        )
        try:
            # 速度調整：改變每幀 duration（GIF）或重新取樣（MP4）
            fps_out = max(1, int(self._fps * speed))
            if fmt == "gif":
                encode_gif(frames, out_path, fps_out,
                           self._cfg["gif"]["colors"],
                           self._cfg["gif"]["dithering"])
            else:
                encode_mp4(frames, out_path, fps_out,
                           self._cfg["mp4"]["crf"], ffmpeg)
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
```

- [ ] **Step 2：執行並測試影像編輯 Tab**

```bash
venv\Scripts\python src\main.py
```

測試步驟：
1. 點「影像編輯」Tab
2. 點「開啟」載入一個 GIF 或 MP4
3. 確認預覽 Canvas 顯示畫面、資訊列正確
4. 拖動起始/結束滑桿，確認預覽跳到對應 frame
5. 點「播放選取範圍」確認動畫播放
6. 點「✂ 匯出」，確認輸出結果顯示

- [ ] **Step 3：Commit**

```bash
git add src/editor.py
git commit -m "feat: complete editor tab with preview, trim, speed and export"
```

---

## Task 9：launcher.ps1 + BAT + README

**Files:**
- Create: `launcher.ps1`
- Modify: `SnapGIFClip啟動器.bat`（已存在，確認內容）
- Create: `README.md`
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/CHANGELOG.md`
- Create: `docs/PITFALLS.md`
- Create: `docs/TODO.md`

- [ ] **Step 1：建立 `launcher.ps1`**

```powershell
# SnapGIFClip 啟動器

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$host.UI.RawUI.WindowTitle = "SnapGIFClip"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Clear-Host
Write-Host "[INFO] Starting SnapGIFClip..." -ForegroundColor Green
Write-Host ""

# ======================================
# [1/4] 檢查 Python
# ======================================
Write-Host "[1/4] 檢查 Python 環境..." -ForegroundColor Cyan
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[WARNING] 未偵測到 Python。" -ForegroundColor Yellow
    $ans = Read-Host "是否要立即安裝 Python？[Y/n] - 直接按 Enter 代表同意"
    if ($ans -eq "" -or $ans -ieq "Y") {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            winget install --id Python.Python.3 -e --silent --accept-source-agreements --accept-package-agreements
        } else {
            Write-Host "[ERROR] 請手動至 https://www.python.org/ 下載安裝後重新執行。" -ForegroundColor Red
            Read-Host "按 Enter 關閉"; exit 1
        }
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
        if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
            Write-Host "[INFO] 請關閉後重新點兩下啟動檔。" -ForegroundColor Yellow
            Read-Host "按 Enter 關閉"; exit 0
        }
    } else { Write-Host "已取消。"; Read-Host "按 Enter 關閉"; exit 1 }
} else {
    Write-Host "[OK] $(python --version) 已安裝。" -ForegroundColor Green
}

# ======================================
# [2/4] 檢查 uv
# ======================================
Write-Host "[2/4] 檢查 uv..." -ForegroundColor Cyan
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] 安裝 uv..." -ForegroundColor Gray
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","User") + ";" + $env:PATH
}
Write-Host "[OK] uv 就緒。" -ForegroundColor Green

# ======================================
# [3/4] 檢查虛擬環境
# ======================================
Write-Host "[3/4] 檢查虛擬環境..." -ForegroundColor Cyan
if (-not (Test-Path "venv")) {
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "    SnapGIFClip - 首次安裝說明" -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  接下來程式會自動幫你安裝以下東西：" -ForegroundColor White
    Write-Host ""
    Write-Host "    1. Python 虛擬環境（venv）" -ForegroundColor Yellow
    Write-Host "       讓這個工具有獨立乾淨的執行空間" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    2. mss" -ForegroundColor Yellow
    Write-Host "       高效率螢幕截圖，用於錄製畫面" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    3. Pillow + imageio" -ForegroundColor Yellow
    Write-Host "       圖片處理與 GIF 輸出" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    4. pynput" -ForegroundColor Yellow
    Write-Host "       快捷鍵監聽" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    5. sv-ttk" -ForegroundColor Yellow
    Write-Host "       Windows 11 風格 UI 主題（可選）" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  全程只需要一直按 Enter 同意即可。" -ForegroundColor Green
    Write-Host "  如果有任何疑問，可以把這段說明貼給 AI 詢問。" -ForegroundColor Green
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    $ans = Read-Host "[WARNING] 找不到虛擬環境，現在建立並安裝套件？[Y/n]"
    if ($ans -eq "" -or $ans -ieq "Y") {
        uv venv venv
        uv pip install -r requirements.txt --python venv\Scripts\python.exe
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] 套件安裝失敗。" -ForegroundColor Red
            Read-Host "按 Enter 關閉"; exit 1
        }
        Write-Host "[OK] 套件安裝完成。" -ForegroundColor Green
    } else { Write-Host "已取消。"; Read-Host "按 Enter 關閉"; exit 1 }
} else {
    $broken = Get-ChildItem "venv\Lib\site-packages" -Directory -Filter "*dist-info" -ErrorAction SilentlyContinue | Where-Object {
        -not (Test-Path (Join-Path $_.FullName "METADATA"))
    }
    foreach ($dir in $broken) { Remove-Item -Recurse -Force $dir.FullName }
    uv pip install -r requirements.txt --python venv\Scripts\python.exe -q
    Write-Host "[OK] 虛擬環境就緒。" -ForegroundColor Green
}

# ======================================
# [4/4] 檢查 ffmpeg
# ======================================
Write-Host "[4/4] 檢查 ffmpeg..." -ForegroundColor Cyan
$ffmpegPath = Join-Path $ScriptDir "bin\ffmpeg.exe"
if (-not (Test-Path $ffmpegPath)) {
    Write-Host ""
    Write-Host "  !! 缺少元件：ffmpeg" -ForegroundColor Yellow
    Write-Host "     ffmpeg 是 MP4 輸出所需的影片處理工具，約 80 MB。" -ForegroundColor Gray
    Write-Host "     如果不需要 MP4 輸出，可以跳過；GIF 功能不受影響。" -ForegroundColor Gray
    Write-Host "     如果有任何疑問，可以把這段說明貼給 AI 詢問。" -ForegroundColor Gray
    Write-Host ""
    $ans = Read-Host "是否要立即下載 ffmpeg？[Y/n] - 直接按 Enter 代表同意"
    if ($ans -eq "" -or $ans -ieq "Y") {
        $ffmpegZip = Join-Path $env:TEMP "ffmpeg.zip"
        $ffmpegUrl = "https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-essentials_build.zip"
        Write-Host "[INFO] 下載中，請稍候..." -ForegroundColor Gray
        try {
            Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZip -UseBasicParsing
            Write-Host "[INFO] 解壓縮中..." -ForegroundColor Gray
            $extractDir = Join-Path $env:TEMP "ffmpeg_extract"
            Expand-Archive -Path $ffmpegZip -DestinationPath $extractDir -Force
            $ffmpegExe = Get-ChildItem -Path $extractDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
            if ($ffmpegExe) {
                $binDir = Join-Path $ScriptDir "bin"
                if (-not (Test-Path $binDir)) { New-Item -ItemType Directory -Force $binDir | Out-Null }
                Copy-Item $ffmpegExe.FullName $ffmpegPath -Force
                Write-Host "[OK] ffmpeg 安裝完成。" -ForegroundColor Green
            } else {
                Write-Host "[WARNING] 找不到 ffmpeg.exe，MP4 功能將停用。" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "[WARNING] ffmpeg 下載失敗，MP4 功能將停用。請確認網路連線。" -ForegroundColor Yellow
        } finally {
            Remove-Item $ffmpegZip -ErrorAction SilentlyContinue
            Remove-Item $extractDir -Recurse -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "[INFO] 跳過 ffmpeg，MP4 功能停用。" -ForegroundColor Gray
    }
} else {
    Write-Host "[OK] ffmpeg 已就緒。" -ForegroundColor Green
}

. ".\venv\Scripts\Activate.ps1"

Write-Host ""
Write-Host "[START] 啟動中，請保持此視窗開啟..." -ForegroundColor Green
Write-Host ""

python src\main.py
$exitCode = $LASTEXITCODE

if (Test-Path "src\__pycache__") { Remove-Item -Recurse -Force "src\__pycache__" }

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] 程式意外停止，請回報上方錯誤訊息。" -ForegroundColor Red
    Read-Host "按 Enter 關閉"
} else {
    Write-Host ""
    Write-Host "5 秒後自動關閉..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
}
```

- [ ] **Step 2：補 UTF-8 BOM 到 launcher.ps1**

```powershell
$path = "C:\Users\CTH\Documents\Code\Snap GIF Creator\launcher.ps1"
$content = Get-Content $path -Raw -Encoding UTF8
$utf8Bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText($path, $content, $utf8Bom)
```

- [ ] **Step 3：建立 `README.md`（根目錄）**

```markdown
/*  ================================  *\
 *                                    *
 *          C  T  H                   *
 *        created by CTH              *
 *                                    *
\*  ================================  */

規則檔: windows-tool.md

# SnapGIFClip

按下快捷鍵框選螢幕區域，錄製成 GIF 或 MP4。內建影像編輯功能可對輸出做裁切與調速。

## 使用方式

雙擊 `SnapGIFClip啟動器.bat` 即可。

## 快速上手

1. 開啟程式後，預設快捷鍵為 `Ctrl+Shift+G`
2. 按下快捷鍵 → 全螢幕暗幕出現，拖拉選取錄製區域
3. 等倒數結束後自動開始錄製（或在設定關閉倒數）
4. 錄製完畢後，GIF/MP4 自動儲存到設定的輸出資料夾
5. 「影像編輯」Tab 可載入任意 GIF/MP4 做裁切與調速
```

- [ ] **Step 4：建立 docs/ 下的 MD 文件**

`docs/ARCHITECTURE.md`：描述目錄結構、模組職責、執行流程（可參考設計文件 `docs/superpowers/specs/2026-05-26-snapgifclip-design.md`）

`docs/CHANGELOG.md`：
```markdown
# CHANGELOG

## 目前狀態
- 錄製：mss + Pillow + ffmpeg，支援 GIF/MP4
- 影像編輯：載入 GIF/MP4，裁切/調速後匯出

## 2026-05-26
- 初始版本建立
```

`docs/PITFALLS.md`：
```markdown
# PITFALLS

初始版本，遇到問題再累積。
```

`docs/TODO.md`：
```markdown
# TODO

- [ ] 多螢幕環境測試（座標系統確認）
- [ ] GIF 品質微調（針對特定內容最佳化色彩數）
```

- [ ] **Step 5：執行完整測試套件**

```bash
venv\Scripts\python -m pytest tests/ -v
```

預期：全部 PASS（test_encode_mp4 因 ffmpeg 未下載可 SKIP）

- [ ] **Step 6：雙擊啟動器做端對端測試**

雙擊 `SnapGIFClip啟動器.bat`，確認：
1. 首次執行時顯示安裝說明
2. ffmpeg 下載後 `bin/ffmpeg.exe` 存在
3. 程式正常啟動，所有功能可用

- [ ] **Step 7：Commit**

```bash
git add launcher.ps1 README.md docs/
git commit -m "feat: launcher with ffmpeg auto-download and project docs"
```

---

## 自審結果

**Spec 覆蓋檢查：**
- ✅ 全螢幕暗幕框選 → Task 4
- ✅ 紅框確認 → Task 4
- ✅ 預設秒數 + 手動停止 → Task 7
- ✅ 倒數 3 秒開關 → Task 4 / Task 6
- ✅ 輸出格式選擇（GIF/MP4/both） → Task 7
- ✅ GIF/MP4 品質控制 → Task 6（進階設定）
- ✅ FPS / 縮放設定 → Task 6
- ✅ 影像編輯 Tab → Task 8
- ✅ 播放速度 + 裁切範圍 → Task 8
- ✅ 容量估算 → Task 5 / Task 8
- ✅ ffmpeg 自動下載 → Task 9
- ✅ 設定自動儲存 → Task 6
- ✅ 快捷鍵可設定 → Task 6
- ✅ CTH Banner → Task 6（`show_cth_banner()`）

**型別一致性：**
- `encode_gif` / `encode_mp4` 在 Task 3 定義，Task 8 `_do_export` 正確引用 ✅
- `calc_output_duration` / `estimate_*` 在 Task 5 定義，Task 8 `_update_size_estimate` 正確引用 ✅
- `Recorder.on_done` 簽名 `(paths: list[str], error: str | None)` 在 Task 3 定義，Task 7 `_handle_msg` 正確解包 ✅
