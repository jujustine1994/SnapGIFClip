import os, sys
import pytest
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
