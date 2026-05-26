"""SnapGIFClip 截圖擷幀與 GIF/MP4 編碼模組。"""
import os
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime

from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(SCRIPT_DIR, "..", "bin")
_bin_ffmpeg = os.path.join(BIN_DIR, "ffmpeg.exe")
DEFAULT_FFMPEG = _bin_ffmpeg if os.path.exists(_bin_ffmpeg) else (shutil.which("ffmpeg") or _bin_ffmpeg)


# ---- 純編碼函式（可獨立測試） ----

def encode_gif(frames: list, output_path: str, fps: int,
               colors: int, dithering: bool):
    """給定 PIL Image 列表，輸出 GIF 到 output_path。"""
    if not frames:
        raise ValueError("frames is empty")
    duration_ms = int(1000 / fps)
    dither_mode = Image.Dither.FLOYDSTEINBERG if dithering else Image.Dither.NONE
    converted = [
        f.convert("P", palette=Image.Palette.ADAPTIVE,
                  colors=colors, dither=dither_mode)
        for f in frames
    ]
    converted[0].save(
        output_path,
        save_all=True,
        append_images=converted[1:],
        loop=0,
        duration=duration_ms,
        optimize=True,
    )


def encode_mp4(frames: list, output_path: str, fps: int,
               crf: int, ffmpeg_path: str = DEFAULT_FFMPEG):
    """給定 PIL Image 列表，輸出 MP4 到 output_path（需要 ffmpeg）。"""
    tmp_dir = tempfile.mkdtemp()
    try:
        for i, frame in enumerate(frames):
            frame.save(os.path.join(tmp_dir, f"frame_{i:06d}.png"))
        cmd = [
            ffmpeg_path, "-y",
            "-framerate", str(fps),
            "-i", os.path.join(tmp_dir, "frame_%06d.png"),
            "-c:v", "libx264",
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg 錯誤：{result.stderr[-500:]}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---- 擷幀錄製器 ----

class Recorder:
    """
    背景執行緒錄製器。
    呼叫 start() 開始；呼叫 stop() 或等待 duration 秒後自動停止；
    完成後透過 on_done(paths, error) 回呼。
    """

    def __init__(self, region: dict, fps: int, scale: float,
                 duration: int, output_folder: str, output_format: str,
                 gif_colors: int, gif_dither: bool, mp4_crf: int,
                 on_progress=None, on_done=None,
                 ffmpeg_path: str = DEFAULT_FFMPEG):
        """
        region: {"top": y1, "left": x1, "width": w, "height": h}
        output_format: "gif" | "mp4" | "both"
        on_progress: callback(elapsed_secs: float)
        on_done: callback(paths: list[str], error: str | None)
        """
        self.region = region
        self.fps = fps
        self.scale = scale
        self.duration = duration
        self.output_folder = output_folder
        self.output_format = output_format
        self.gif_colors = gif_colors
        self.gif_dither = gif_dither
        self.mp4_crf = mp4_crf
        self.on_progress = on_progress
        self.on_done = on_done
        self.ffmpeg_path = ffmpeg_path
        self._stop_event = threading.Event()

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        import mss
        frames = []
        interval = 1.0 / self.fps
        start_time = time.time()

        with mss.mss() as sct:
            while not self._stop_event.is_set():
                elapsed = time.time() - start_time
                if elapsed >= self.duration:
                    break
                frame_start = time.time()
                raw = sct.grab(self.region)
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                if self.scale != 1.0:
                    nw = max(2, int(img.width * self.scale))
                    nh = max(2, int(img.height * self.scale))
                    img = img.resize((nw, nh), Image.LANCZOS)
                frames.append(img)
                if self.on_progress:
                    self.on_progress(elapsed)
                sleep = interval - (time.time() - frame_start)
                if sleep > 0:
                    time.sleep(sleep)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        paths, error = [], None
        try:
            os.makedirs(self.output_folder, exist_ok=True)
            if self.output_format in ("gif", "both"):
                p = os.path.join(self.output_folder, f"snap_{timestamp}.gif")
                encode_gif(frames, p, self.fps, self.gif_colors, self.gif_dither)
                paths.append(p)
            if self.output_format in ("mp4", "both"):
                p = os.path.join(self.output_folder, f"snap_{timestamp}.mp4")
                encode_mp4(frames, p, self.fps, self.mp4_crf, self.ffmpeg_path)
                paths.append(p)
        except Exception as e:
            error = str(e)

        if self.on_done:
            self.on_done(paths, error)
