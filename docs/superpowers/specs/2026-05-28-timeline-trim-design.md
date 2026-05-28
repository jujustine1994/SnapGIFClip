# 設計文件：Filmstrip 時間軸裁切介面

日期：2026-05-28  
模組：`src/editor.py`  
狀態：已核准，待實作

---

## 目標

將影像編輯頁的時間範圍裁切操作從「兩條獨立滑桿」升級為視覺化時間軸，讓使用者可以直覺拖拉縮圖條來選取範圍，同時保留數值精確輸入。

---

## 佈局變化

### 左側面板

在預覽 Canvas 和播放按鈕之間，插入一條 `TimelineCanvas`（固定高度 70px）：

```
載入檔案
────────────────────────────
預覽 Canvas（fill + expand）
────────────────────────────
時間軸 Canvas（70px 固定高）
────────────────────────────
▶ 播放選取範圍   0.0 / 5.0 秒
```

### 右側面板（裁切範圍區）

移除兩條 `ttk.Scale` 滑桿，改為秒數輸入框 + 微調按鈕：

```
起始：[ ◀ ][ 1.2 ]秒[ ▶ ]
結束：[ ◀ ][ 4.8 ]秒[ ▶ ]
→ 選取時長：3.6 秒
```

- ◀ ▶ 每次步進 ±0.1 秒
- 輸入框支援直接鍵入，按 Enter 或失焦後生效

---

## TimelineCanvas 類別

新增於 `editor.py`，封裝所有時間軸 UI 與互動邏輯。

### Filmstrip 縮圖

- 載入影片後，從 `self._frames` 等間距抽樣，填滿時間軸寬度
- 每格縮圖約 60px 寬 × 55px 高
- 視窗尺寸改變（`<Configure>`）時重新抽樣並重繪
- 所有 `ImageTk.PhotoImage` 物件存在 list 中，防止被 GC 回收

### 視覺元素

```
0s              2s              5s
┌──┬──┬──┬──┬──┬──┬──┬──┬──┬──┐
│▓▓│▓▓│▓▓│██│██│██│██│▓▓│▓▓│▓▓│  ← 縮圖
└──┴──┴──┴──┴──┴──┴──┴──┴──┴──┘
         ●[            ]●          ← 選取框 + 把手
```

- **非選取區**：疊加 `stipple="gray50"` 暗化遮罩
- **選取框**：`stipple="gray25"` 藍色填色（#3498db），模擬半透明
- **把手**：8px 寬實心色塊（#2980b9），上下延伸滿整個軌道高度
- **時間刻度**：在縮圖下方顯示秒數標記（每 N 秒一格，依總時長自動計算間距）

### 拖動互動

| 點擊位置 | 模式 | 行為 |
|---------|------|------|
| 左把手（中心 ±8px） | `left` | 拖動改變起始時間 |
| 右把手（中心 ±8px） | `right` | 拖動改變結束時間 |
| 中間選取區 | `middle` | 整體平移，保持選取時長不變 |
| 選取區外空白 | 無 | 無反應 |

- 拖動中，滑鼠游標依模式切換（`←→` / `⟺` / default）
- 起始不可超過結束（最小間距 0.1 秒）
- 平移模式不可超出影片頭尾邊界

### 對外介面

```python
timeline.load(frames, fps, total_secs)  # 載入後呼叫，生成縮圖
timeline.set_range(start, end)          # 外部同步 → 更新 overlay 位置
on_range_change(start, end)             # callback，時間軸拖動後呼叫
```

---

## 資料流

單一真實來源：`self._start_var` / `self._end_var`（`tk.DoubleVar`）

```
拖動時間軸把手     → on_range_change(s, e) callback
                       └─→ _start_var.set(s) / _end_var.set(e)
Entry 輸入 + Enter → 解析 + clamp
                       └─→ _start_var.set() / _end_var.set()
點擊 ◀ ▶ 按鈕     → 讀取 ± 0.1 + clamp
                       └─→ _start_var.set() / _end_var.set()

DoubleVar.trace("write") 統一觸發 _on_trim_change()
  ├─ 更新 Entry 顯示文字（若 Entry 未在 focus 中）
  ├─ timeline.set_range(start, end)   ← 同步 overlay（不會再觸發 callback）
  ├─ _show_frame(start_frame_idx)
  └─ debounce 500ms → _update_size_estimate()
```

### 輸入框防覆寫

- 以 `focus_get()` 判斷 Entry 是否在 focus 中
- 若是，`_on_trim_change` 跳過更新該 Entry 的文字（避免打字中途被覆蓋）

### 非法輸入處理

- 輸入非數字或超出 `[0, total_secs]` 範圍 → 自動 clamp 回合法值
- Entry 背景閃紅 0.5 秒做視覺提示

---

## 實作範圍

**修改檔案**：`src/editor.py` 僅此一個檔案

**新增**：
- `TimelineCanvas` class（約 150-180 行）
- `_build_trim_entries()` 方法（建立輸入框 + 微調按鈕）

**移除**：
- `self._start_scale`、`self._end_scale`（兩條 `ttk.Scale`）
- `self._start_label`、`self._end_label`（秒數標籤，改由 Entry 顯示）

**保留不動**：
- `_start_var`、`_end_var`（DoubleVar，仍是真實來源）
- `_on_trim_change()`（邏輯不變，只新增 timeline 同步呼叫）
- 其他所有匯出、播放、速度調整邏輯

---

## 不在本次範圍內

- 播放進度指針（播放時時間軸上顯示目前播放位置）
- 縮圖快取（每次載入都重新生成，不持久化）
- 鍵盤快捷鍵操作時間軸
