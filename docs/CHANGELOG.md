# CHANGELOG

## 目前狀態
- 錄製：mss + Pillow + ffmpeg，支援 GIF/MP4
- 影像編輯：載入 GIF/MP4，裁切/調速後匯出

## 2026-05-28
- refactor: 輸出資料夾從設定頁移至主工作頁（輸出格式與錄製模式之間）
- fix: _discard_recording() 立即銷毀紅框，與 _stop_recording() 行為一致
- fix: 輸出格式選擇現在儲存至 config，重啟後不重置
- fix: editor 載入成功時重置 info_label 顏色（避免殘留紅色錯誤狀態）
- fix: config.py 統一使用模組層級 CONFIG_PATH，移除三處重複的環境變數讀取
- chore: 移除 imageio（未使用的 dependency）
- chore: 移除所有說明 WHAT 的 inline 備註與 stale task 備註

## 2026-05-27
- fix: recorder._run() 加頂層 try-except，確保任何例外都會呼叫 on_done，避免紅框卡死
- fix: 按下快捷鍵停止時立即銷毀紅框，不等編碼完成；label 顯示「編碼中，請稍候」
- feat: 錄製完成（或失敗）後彈出 Windows 系統通知（balloon tip）

## 2026-05-26
- 初始版本建立
- fix: encode_mp4 加 `-vf scale=trunc(iw/2)*2:trunc(ih/2)*2` 修正 yuv420p 需偶數寬高的錯誤
- feat: 錄製進度區新增「廢棄」按鈕，可在錄製中途放棄並跳過編碼
