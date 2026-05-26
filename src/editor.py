"""SnapGIFClip 影像編輯模組：純邏輯 + EditorTab UI。"""
import math


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
