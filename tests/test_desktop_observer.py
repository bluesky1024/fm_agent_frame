from apps.minesweeper import BoardGeometry, BoardObserver
from PIL import Image

from agent_frame.capabilities.computer_use import CaptureRegion, ScreenCapture


class FakeBackend:
    def grab(self, region: CaptureRegion) -> Image.Image:
        return Image.new("RGB", (region.width, region.height), "white")


def _capture(left=0, top=0, w=200, h=200) -> ScreenCapture:
    region = CaptureRegion(left=left, top=top, width=w, height=h)
    return ScreenCapture(region, backend=FakeBackend())


def _geo(origin_x=20, origin_y=20) -> BoardGeometry:
    return BoardGeometry(origin_x=origin_x, origin_y=origin_y, cell_w=10, cell_h=10, rows=9, cols=9)


async def test_observe_returns_image_user_message():
    obs = BoardObserver(_capture(), _geo(), mines=3)
    msg = await obs.observe()

    assert msg.role == "user"
    assert isinstance(msg.content, list)
    text_part, image_part = msg.content
    assert "棋盘" in text_part.text
    assert "本局共 3 颗雷" in text_part.text
    assert "已翻开 78 格才算胜利" in text_part.text
    assert image_part.type == "image_url"
    assert image_part.image_url["url"].startswith("data:image/png;base64,")
    assert image_part.image_url["detail"] == "high"


async def test_observe_keeps_last_raw_image_for_probing():
    obs = BoardObserver(_capture(), _geo(), mines=3)
    assert obs.last_image is None

    await obs.observe()

    assert obs.last_image is not None
    assert obs.last_image.size == (200, 200)


async def test_observe_offsets_geometry_into_image_space():
    # 截屏区域从 (50,60) 开始，几何原点也是 (50,60) → 图像空间应为 (0,0)
    obs = BoardObserver(_capture(left=50, top=60, w=100, h=100), _geo(50, 60), mines=3)
    assert obs.annotator is not None
    assert obs.annotator.geometry.origin_x == 0
    assert obs.annotator.geometry.origin_y == 0
