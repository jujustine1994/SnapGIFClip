# CHANGELOG

## 目前狀態
- 錄製：mss + Pillow + ffmpeg，支援 GIF/MP4
- 影像編輯：載入 GIF/MP4，裁切/調速後匯出

## 2026-05-26
- 初始版本建立
- fix: encode_mp4 加 `-vf scale=trunc(iw/2)*2:trunc(ih/2)*2` 修正 yuv420p 需偶數寬高的錯誤
- feat: 錄製進度區新增「廢棄」按鈕，可在錄製中途放棄並跳過編碼
