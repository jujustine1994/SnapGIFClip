import json
import os
import tempfile
import pytest

# 暫時替換 CONFIG_PATH 再 import
os.environ["SNAPGIFCLIP_CONFIG"] = ""


def test_load_defaults_when_missing(tmp_path, monkeypatch):
    cfg_path = str(tmp_path / "config.json")
    monkeypatch.setenv("SNAPGIFCLIP_CONFIG", cfg_path)
    import importlib
    import src.config as c
    importlib.reload(c)
    result = c.load()
    assert result["fps"] == 15
    assert result["scale"] == 1.0
    assert result["countdown"] is True
    assert result["gif"]["colors"] == 256


def test_save_and_reload(tmp_path, monkeypatch):
    cfg_path = str(tmp_path / "config.json")
    monkeypatch.setenv("SNAPGIFCLIP_CONFIG", cfg_path)
    import importlib
    import src.config as c
    importlib.reload(c)
    c.save({"fps": 10, "scale": 0.5, "countdown": False,
            "gif": {"colors": 128, "dithering": False},
            "mp4": {"crf": 28},
            "output_folder": "C:\\test",
            "hotkey": "ctrl+shift+g",
            "default_duration": 5})
    result = c.load()
    assert result["fps"] == 10
    assert result["gif"]["colors"] == 128


def test_load_merges_missing_keys(tmp_path, monkeypatch):
    cfg_path = str(tmp_path / "config.json")
    with open(cfg_path, "w") as f:
        json.dump({"fps": 20}, f)
    monkeypatch.setenv("SNAPGIFCLIP_CONFIG", cfg_path)
    import importlib
    import src.config as c
    importlib.reload(c)
    result = c.load()
    assert result["fps"] == 20
    assert result["scale"] == 1.0   # default 補上
