import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.editor import calc_output_duration, estimate_gif_size, estimate_mp4_size, TimelineCanvas


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


def test_time_to_x_basic():
    # 5 秒影片，畫布寬 500px，2.5 秒應在 x=250
    assert TimelineCanvas.time_to_x(t=2.5, total=5.0, width=500) == 250


def test_time_to_x_over_boundary():
    # 超出邊界只截斷，不報錯
    assert TimelineCanvas.time_to_x(t=6.0, total=5.0, width=500) == 600  # 超出不 clamp


def test_x_to_time_basic():
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
