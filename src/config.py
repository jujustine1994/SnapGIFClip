"""SnapGIFClip 設定讀寫模組。"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("SNAPGIFCLIP_CONFIG") or os.path.join(SCRIPT_DIR, "config.json")

DEFAULT = {
    "output_folder": os.path.join(os.path.expanduser("~"), "Desktop"),
    "hotkey": "ctrl+shift+g",
    "record_mode": "fixed",
    "default_duration": 10,
    "fps": 15,
    "scale": 1.0,
    "countdown": True,
    "output_format": "both",
    "gif": {"colors": 256, "dithering": True},
    "mp4": {"crf": 23},
}


def load() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        merged = dict(DEFAULT)
        merged.update(raw)
        merged["gif"] = {**DEFAULT["gif"], **raw.get("gif", {})}
        merged["mp4"] = {**DEFAULT["mp4"], **raw.get("mp4", {})}
        return merged
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT)


def save(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def update(**kwargs):
    cfg = load()
    cfg.update(kwargs)
    save(cfg)
