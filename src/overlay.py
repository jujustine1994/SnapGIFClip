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
