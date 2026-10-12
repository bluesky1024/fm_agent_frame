from PIL import Image

from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.observer import BoardObserver
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture


def _capture(left=0, top=0, w=200, h=200) -> ScreenCapture:
    region = CaptureRegion(left=left, top=top, width=w, height=h)
    return ScreenCapture(
        region, grabber=lambda r: Image.new("RGB", (r.width, r.height), "white")
    )


def _geo(origin_x=20, origin_y=20) -> BoardGeometry:
    return BoardGeometry(
        origin_x=origin_x, origin_y=origin_y, cell_w=10, cell_h=10, rows=9, cols=9
    )


async def test_observe_returns_image_user_message():
    obs = BoardObserver(_capture(), _geo())
    msg = await obs.observe()

    assert msg.role == "user"
    assert isinstance(msg.content, list)
    text_part, image_part = msg.content
    assert "棋盘" in text_part.text
    assert image_part.type == "image_url"
    assert image_part.image_url["url"].startswith("data:image/png;base64,")
    assert image_part.image_url["detail"] == "high"


async def test_observe_offsets_geometry_into_image_space():
    # 截屏区域从 (50,60) 开始，几何原点也是 (50,60) → 图像空间应为 (0,0)
    obs = BoardObserver(_capture(left=50, top=60, w=100, h=100), _geo(50, 60))
    assert obs.annotator.geometry.origin_x == 0
    assert obs.annotator.geometry.origin_y == 0
