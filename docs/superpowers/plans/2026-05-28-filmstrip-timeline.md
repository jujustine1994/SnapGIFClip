# Filmstrip Timeline Trim 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在影像編輯頁預覽下方加入可拖拉的 Filmstrip 時間軸，並將右側滑桿換成秒數輸入框 + 微調按鈕，兩者雙向連動。

**Architecture:** 在 `src/editor.py` 新增 `TimelineCanvas` class 封裝所有時間軸邏輯（縮圖生成、選取框繪製、拖拉互動）；EditorTab 的 `_start_var`/`_end_var`（DoubleVar）維持單一真實來源，所有操作統一透過 DoubleVar trace 觸發 `_on_trim_change`。

**Tech Stack:** Python 3、tkinter（Canvas、DoubleVar trace）、Pillow（ImageTk.PhotoImage）

---

## 檔案異動一覽

| 檔案 | 異動 |
|------|------|
| `src/editor.py` | 新增 `TimelineCanvas` class；修改 `EditorTab._build_ui`、`_on_frames_loaded`、`_on_trim_change` |
| `tests/test_editor.py` | 新增 `TimelineCanvas` 靜態 helper 的單元測試 |

---

### Task 1：TimelineCanvas 骨架 + 純函式 helpers + 測試

**Files:**
- Modify: `src/editor.py`
- Modify: `tests/test_editor.py`

- [ ] **Step 1：先在 `tests/test_editor.py` 補 import 並寫三個失敗測試**

在檔案最上方 import 行加上 `TimelineCanvas`，然後在檔尾新增：

```python
from src.editor import calc_output_duration, estimate_gif_size, estimate_mp4_size, TimelineCanvas


def test_time_to_x_basic():
    # 5 秒影片，畫布寬 500px，2.5 秒應在 x=250
    assert TimelineCanvas.time_to_x(t=2.5, total=5.0, width=500) == 250


def test_time_to_x_clamp():
    # 超出邊界只截斷，不報錯
    assert TimelineCanvas.time_to_x(t=6.0, total=5.0, width=500) == 600  # 超出不 clamp


def test_x_to_time_basic():
    import pytest
    assert TimelineCanvas.x_to_time(x=250, total=5.0, width=500) == pytest.approx(2.5)


def test_x_to_time_clamp_low():
    assert TimelineCanvas.x_to_time(x=-10, total=5.0, width=500) == pytest.approx(0.0)


def test_x_to_time_clamp_high():
    assert TimelineCanvas.x_to_time(x=600, total=5.0, width=500) == pytest.approx(5.0)


def test_get_drag_mode_left_handle():
    # sx=100, ex=400, handle_w=8 → x=105 應命中左把手
    assert TimelineCanvas.get_drag_mode(x=105, sx=100, ex=400, handle_w=8) == "left"


def test_get_drag_mode_right_handle():
    assert TimelineCanvas.get_drag_mode(x=395, sx=100, ex=400, handle_w=8) == "right"


def test_get_drag_mode_middle():
    assert TimelineCanvas.get_drag_mode(x=250, sx=100, ex=400, handle_w=8) == "middle"


def test_get_drag_mode_outside():
    assert TimelineCanvas.get_drag_mode(x=50, sx=100, ex=400, handle_w=8) is None
```

- [ ] **Step 2：確認測試失敗（TimelineCanvas 尚未建立）**

```
cd "C:\Users\CTH\Documents\Code\Snap GIF Creator"
.venv\Scripts\python.exe -m pytest tests/test_editor.py -v 2>&1 | tail -20
```

預期：`ImportError: cannot import name 'TimelineCanvas'`

- [ ] **Step 3：在 `src/editor.py` 的 `EditorTab` class 定義前，新增 `TimelineCanvas` class 骨架**

在 `class EditorTab:` 上方（約第 45 行）插入：

```python
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
        return int(t / total * width)

    @staticmethod
    def x_to_time(x: int, total: float, width: int) -> float:
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
        pass  # Task 2 實作

    def _redraw(self) -> None:
        self._canvas.delete("all")

    def _draw_overlay(self) -> None:
        pass  # Task 3 實作

    def _on_resize(self, _event) -> None:
        pass  # Task 2 實作

    def _on_press(self, event) -> None:
        pass  # Task 4 實作

    def _on_drag(self, event) -> None:
        pass  # Task 4 實作

    def _on_release(self, _event) -> None:
        self._drag_mode = None

    def _on_hover(self, event) -> None:
        pass  # Task 4 實作
```

- [ ] **Step 4：確認測試通過**

```
.venv\Scripts\python.exe -m pytest tests/test_editor.py -v 2>&1 | tail -20
```

預期：所有測試 PASS

- [ ] **Step 5：Commit**

```
git add src/editor.py tests/test_editor.py
git commit -m "feat: add TimelineCanvas skeleton with pure helpers + tests"
```

---

### Task 2：Filmstrip 縮圖生成與繪製

**Files:**
- Modify: `src/editor.py`（`TimelineCanvas._generate_thumbnails`、`_draw_filmstrip`、`_draw_tick_marks`、`_redraw`、`_on_resize`）

- [ ] **Step 1：實作 `_generate_thumbnails`**

將 `src/editor.py` 的 `TimelineCanvas._generate_thumbnails` stub 替換為：

```python
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
```

- [ ] **Step 2：實作 `_draw_filmstrip` 和 `_draw_tick_marks`，並更新 `_redraw`**

在 `_generate_thumbnails` 下方新增：

```python
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
```

將 `_redraw` stub 替換為：

```python
def _redraw(self) -> None:
    self._canvas.delete("all")
    self._draw_filmstrip()
    self._draw_tick_marks()
    self._draw_overlay()
```

將 `_on_resize` stub 替換為：

```python
def _on_resize(self, _event) -> None:
    if self._source_frames:
        self._regen_and_redraw()
```

- [ ] **Step 3：確認既有測試仍然通過**

```
.venv\Scripts\python.exe -m pytest tests/test_editor.py -v 2>&1 | tail -10
```

預期：所有測試 PASS

- [ ] **Step 4：Commit**

```
git add src/editor.py
git commit -m "feat: implement filmstrip thumbnail generation and tick marks"
```

---

### Task 3：選取框 overlay 繪製

**Files:**
- Modify: `src/editor.py`（`TimelineCanvas._draw_overlay`）

- [ ] **Step 1：實作 `_draw_overlay`**

將 `_draw_overlay` stub 替換為：

```python
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
```

- [ ] **Step 2：確認測試通過**

```
.venv\Scripts\python.exe -m pytest tests/test_editor.py -v 2>&1 | tail -10
```

預期：所有測試 PASS

- [ ] **Step 3：Commit**

```
git add src/editor.py
git commit -m "feat: implement timeline selection overlay with stipple transparency"
```

---

### Task 4：拖拉互動 + 游標切換

**Files:**
- Modify: `src/editor.py`（`TimelineCanvas._on_press`、`_on_drag`、`_on_hover`）

- [ ] **Step 1：實作 `_on_press`**

將 `_on_press` stub 替換為：

```python
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
```

- [ ] **Step 2：實作 `_on_drag`**

將 `_on_drag` stub 替換為：

```python
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
```

- [ ] **Step 3：實作 `_on_hover`**

將 `_on_hover` stub 替換為：

```python
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
```

- [ ] **Step 4：確認測試通過**

```
.venv\Scripts\python.exe -m pytest tests/test_editor.py -v 2>&1 | tail -10
```

預期：所有測試 PASS

- [ ] **Step 5：Commit**

```
git add src/editor.py
git commit -m "feat: implement timeline drag interaction and cursor feedback"
```

---

### Task 5：右側面板—滑桿換成 Entry + 微調按鈕

**Files:**
- Modify: `src/editor.py`（`EditorTab._build_ui`、新增 `_step_time`、`_commit_entry`）

- [ ] **Step 1：移除 `_build_ui` 裡的兩條 Scale（起始/結束），換成 Entry + ◀▶ 按鈕**

找到 `f_trim` 的建立區塊（目前約第 101–123 行），將以下舊程式碼：

```python
        r0 = ttk.Frame(f_trim); r0.pack(fill="x", pady=2)
        ttk.Label(r0, text="起始：", width=5).pack(side="left")
        self._start_scale = ttk.Scale(r0, variable=self._start_var,
                                      from_=0, to=1, orient="horizontal",
                                      command=self._on_trim_change)
        self._start_scale.pack(side="left", fill="x", expand=True)
        self._start_label = ttk.Label(r0, text="0.0 秒", width=7)
        self._start_label.pack(side="left")

        r1 = ttk.Frame(f_trim); r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="結束：", width=5).pack(side="left")
        self._end_scale = ttk.Scale(r1, variable=self._end_var,
                                    from_=0, to=1, orient="horizontal",
                                    command=self._on_trim_change)
        self._end_scale.pack(side="left", fill="x", expand=True)
        self._end_label = ttk.Label(r1, text="0.0 秒", width=7)
        self._end_label.pack(side="left")
```

替換為：

```python
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
```

- [ ] **Step 2：新增 `_step_time` 和 `_commit_entry` 方法**

在 `EditorTab._open_file` 方法前插入：

```python
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
```

- [ ] **Step 3：確認測試通過**

```
.venv\Scripts\python.exe -m pytest tests/test_editor.py -v 2>&1 | tail -10
```

預期：所有測試 PASS

- [ ] **Step 4：Commit**

```
git add src/editor.py
git commit -m "feat: replace trim sliders with Entry + step buttons"
```

---

### Task 6：整合時間軸到 EditorTab + 連動資料流

**Files:**
- Modify: `src/editor.py`（`EditorTab._build_ui`、`_on_frames_loaded`、`_on_trim_change`）

- [ ] **Step 1：在 `_build_ui` 的預覽區塊後插入時間軸，並設定 DoubleVar trace**

找到 `f_preview` pack 完畢的這行：

```python
        self._photo = None
```

在其後插入：

```python
        self._timeline = TimelineCanvas(
            left,
            on_range_change=self._on_timeline_change,
        )
```

然後在 `_build_ui` 結尾（`self._debounce_job = None` 這行）前插入：

```python
        self._start_var.trace_add("write", self._on_trim_change)
        self._end_var.trace_add("write", self._on_trim_change)
```

- [ ] **Step 2：新增 `_on_timeline_change` callback**

在 `_step_time` 方法前插入：

```python
    def _on_timeline_change(self, start: float, end: float) -> None:
        self._start_var.set(round(start, 2))
        self._end_var.set(round(end, 2))
```

- [ ] **Step 3：更新 `_on_frames_loaded`，移除 Scale config，加入 timeline.load**

找到 `_on_frames_loaded` 中這兩行並以 `_timeline.load(...)` 取代（必須在 DoubleVar.set 之前，確保 trace 觸發時 timeline._total 已是新值）：

```python
        self._start_scale.config(to=total)
        self._end_scale.config(to=total)
```

改為：

```python
        self._timeline.load(self._frames, self._fps, self._total_secs)
```

位置：在 `self._start_var.set(0.0)` **之前**（原兩行 Scale config 的原位置）。

- [ ] **Step 4：重寫 `_on_trim_change` 以支援 DoubleVar trace 並同步 Entry + timeline**

將整個 `_on_trim_change` 方法替換為：

```python
    def _on_trim_change(self, *_):
        start = self._start_var.get()
        end = self._end_var.get()
        if start >= end and self._frames:
            end = min(start + 0.1, self._total_secs)
            self._end_var.set(end)
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
```

- [ ] **Step 5：確認所有測試通過**

```
.venv\Scripts\python.exe -m pytest tests/test_editor.py -v 2>&1 | tail -15
```

預期：所有測試 PASS

- [ ] **Step 6：手動啟動程式驗證**

```
.venv\Scripts\python.exe src/main.py
```

驗證清單：
- 開啟一個 GIF 或 MP4 → 時間軸出現縮圖條與藍色選取框
- 拖動左/右把手 → 起始/結束 Entry 數值同步更新
- 拖動中間選取區 → 整體平移，時長不變
- 在 Entry 輸入數字按 Enter → 時間軸 overlay 同步
- 點 ◀ ▶ 按鈕 → 時間軸 overlay 同步
- 輸入非數字按 Enter → Entry 閃紅，恢復原值
- 縮放視窗 → 時間軸縮圖重新生成，選取框位置正確

- [ ] **Step 7：Commit**

```
git add src/editor.py
git commit -m "feat: integrate TimelineCanvas into EditorTab with bidirectional sync"
```
