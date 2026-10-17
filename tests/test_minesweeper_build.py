from apps.minesweeper import (
    BoardGeometry,
    MinesweeperConfig,
    build_agent,
    build_registry,
)
from PIL import Image

from agent_frame.capabilities.computer_use import (
    CaptureRegion,
    MouseController,
    ScreenCapture,
)


class FakeBackend:
    def click(self, x, y, button):
        pass

    def moveTo(self, x, y):
        pass

    def press(self, key):
        pass

    def keyDown(self, key):
        pass

    def keyUp(self, key):
        pass


class _FakeScreenBackend:
    def grab(self, region: CaptureRegion) -> Image.Image:
        return Image.new("RGB", (region.width, region.height), "white")


def _config() -> MinesweeperConfig:
    return MinesweeperConfig(
        geometry=BoardGeometry(origin_x=0, origin_y=0, cell_w=10, cell_h=10, rows=9, cols=9),
        region=CaptureRegion(left=0, top=0, width=100, height=100),
        mines=3,
        image_detail="high",
        image_max_px=1300,
        max_steps=300,
    )


def test_build_registry_has_click_and_flag_tools():
    reg = build_registry(_config(), MouseController(backend=FakeBackend()))
    assert set(reg.names()) == {"click_cell", "flag_cell"}


def test_build_agent_assembles_without_touching_screen():
    cap = ScreenCapture(
        CaptureRegion(left=0, top=0, width=100, height=100),
        backend=_FakeScreenBackend(),
    )
    mouse = MouseController(backend=FakeBackend())
    agent = build_agent(_config(), llm=object(), mouse=mouse, capture=cap)
    assert agent is not None
    assert agent.spec.context_providers[0].placement == "after_history"


def test_config_from_board_config_parses_typed_fields():
    raw = {
        "geometry": {
            "origin_x": 1,
            "origin_y": 2,
            "cell_w": 3,
            "cell_h": 4,
            "rows": 5,
            "cols": 6,
        },
        "region": {"left": 0, "top": 0, "width": 50, "height": 50},
        "mines": 2,
        "image_detail": "low",
        "image_max_px": 800,
    }

    config = MinesweeperConfig.from_board_config(raw, max_steps=42, tool_timeout=1.5)

    assert config.geometry.rows == 5
    assert config.geometry.cols == 6
    assert config.region.width == 50
    assert config.mines == 2
    assert config.image_detail == "low"
    assert config.image_max_px == 800
    assert config.max_steps == 42
    assert config.tool_timeout == 1.5
