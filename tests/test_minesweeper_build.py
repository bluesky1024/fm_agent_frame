import json
import sys

import pytest
from PIL import Image

from agent_frame.desktop.minesweeper import build_agent, build_registry, load_config
from agent_frame.desktop.mouse import MouseController
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture


class FakeBackend:
    def click(self, x, y, button):
        pass

    def moveTo(self, x, y):
        pass

    def press(self, key):
        pass


def _config() -> dict:
    return {
        "geometry": {
            "origin_x": 0,
            "origin_y": 0,
            "cell_w": 10,
            "cell_h": 10,
            "rows": 9,
            "cols": 9,
        },
        "region": {"left": 0, "top": 0, "width": 100, "height": 100},
        "restart": {"type": "click", "x": 50, "y": 50},
        "image_detail": "high",
        "image_max_px": 1300,
        "max_steps": 300,
    }


def test_build_registry_has_three_tools():
    reg = build_registry(_config(), MouseController(backend=FakeBackend()))
    assert set(reg.names()) == {"click_cell", "flag_cell", "restart_game"}


def test_build_registry_supports_key_restart():
    cfg = _config()
    cfg["restart"] = {"type": "key", "key": "f2"}
    reg = build_registry(cfg, MouseController(backend=FakeBackend()))
    assert "restart_game" in reg.names()


def test_build_agent_assembles_without_touching_screen():
    cap = ScreenCapture(
        CaptureRegion(left=0, top=0, width=100, height=100),
        grabber=lambda r: Image.new("RGB", (r.width, r.height), "white"),
    )
    mouse = MouseController(backend=FakeBackend())
    agent = build_agent(_config(), llm=object(), mouse=mouse, capture=cap)
    assert agent is not None


def test_load_config_selects_platform_section(monkeypatch, tmp_path):
    data = {
        "windows": {
            "geometry": {"origin_x": 1, "origin_y": 2, "cell_w": 10, "cell_h": 10, "rows": 9, "cols": 9},
            "region": {"left": 0, "top": 0, "width": 100, "height": 100},
            "restart": {"type": "click", "x": 50, "y": 50},
        },
        "macos": {
            "geometry": {"origin_x": 11, "origin_y": 22, "cell_w": 12, "cell_h": 12, "rows": 9, "cols": 9},
            "region": {"left": 0, "top": 0, "width": 120, "height": 120},
            "restart": {"type": "click", "x": 60, "y": 60},
        },
        "image_detail": "high",
        "image_max_px": 1300,
        "max_steps": 300,
    }
    path = tmp_path / "minesweeper.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(sys, "platform", "darwin")
    cfg = load_config(path)
    assert cfg["geometry"] == data["macos"]["geometry"]
    assert cfg["region"] == data["macos"]["region"]
    assert cfg["image_detail"] == "high"
    assert cfg["image_max_px"] == 1300
    assert cfg["max_steps"] == 300

    monkeypatch.setattr(sys, "platform", "win32")
    cfg = load_config(path)
    assert cfg["geometry"] == data["windows"]["geometry"]


def test_load_config_unknown_platform_raises(monkeypatch, tmp_path):
    data = {
        "windows": {
            "geometry": {"origin_x": 0, "origin_y": 0, "cell_w": 10, "cell_h": 10, "rows": 9, "cols": 9},
            "region": {"left": 0, "top": 0, "width": 100, "height": 100},
            "restart": {"type": "click", "x": 50, "y": 50},
        },
        "image_max_px": 1300,
    }
    path = tmp_path / "minesweeper.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(ValueError):
        load_config(path)


def test_load_config_missing_platform_section_raises(monkeypatch, tmp_path):
    data = {"image_max_px": 1300}  # 缺 windows/macos section
    path = tmp_path / "minesweeper.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(ValueError):
        load_config(path)
