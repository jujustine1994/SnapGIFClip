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
