# ARCHITECTURE

## 目錄結構

```
Snap GIF Creator/
├── SnapGIFClip啟動器.bat   唯一入口（薄殼，2 行）
├── launcher.ps1            環境檢查、ffmpeg 下載、venv 建立、啟動
├── requirements.txt        Python 套件清單
├── bin/
│   └── ffmpeg.exe          由 launcher 自動下載（.gitignore 排除）
├── src/
│   ├── main.py             主視窗、3 Tab、hotkey 監聽、queue 通訊
│   ├── overlay.py          FullscreenOverlay（選框）、RecordingBorder（紅框）
│   ├── recorder.py         mss 截圖迴圈、GIF/MP4 編碼
│   ├── editor.py           影像編輯 Tab：載入、預覽、裁切、調速、估算、匯出
│   ├── config.py           讀寫 src/config.json
│   └── config.json         使用者設定（自動生成，.gitignore 排除）
└── tests/
    ├── test_config.py
    ├── test_recorder.py
    └── test_editor.py
```

## 模組職責

| 模組 | 職責 |
|------|------|
| `main.py` | 主視窗、3 Tab 骨架、pynput 快捷鍵監聽、queue 輪詢 |
| `overlay.py` | 全螢幕選框暗幕（FullscreenOverlay）、錄製紅框（RecordingBorder） |
| `recorder.py` | mss 截圖迴圈（Recorder class）、encode_gif、encode_mp4 |
| `editor.py` | 純計算函式（calc_output_duration、estimate_*）+ EditorTab UI |
| `config.py` | load() / save() / update()，支援環境變數覆寫路徑（測試用） |

## 執行流程

1. 使用者雙擊 BAT → launcher.ps1 檢查環境 → `python src/main.py`
2. 主視窗啟動，pynput 在背景監聽快捷鍵
3. 快捷鍵觸發 → FullscreenOverlay 開啟 → 拖拉選取區域
4. 選取完成 → 倒數（可選）→ RecordingBorder 紅框出現
5. Recorder 在背景執行緒以 mss 逐幀截圖
6. 錄製結束（時限到或手動停止）→ encode_gif / encode_mp4
7. on_done 回呼透過 queue 通知主執行緒 → UI 更新

## 執行緒模型

- 主執行緒：tkinter mainloop + queue 輪詢（每 100ms）
- 錄製執行緒：Recorder._run()，透過 msg_queue 傳訊給主執行緒
- 影像編輯載入執行緒：EditorTab._load_frames()
- 影像編輯匯出執行緒：EditorTab._do_export()
