from PIL import Image

from agent_frame.desktop.screen import CaptureRegion, ScreenCapture


def test_grab_delegates_to_grabber_with_region():
    region = CaptureRegion(left=10, top=20, width=30, height=40)
    seen = {}

    def fake_grabber(r):
        seen["region"] = r
        return Image.new("RGB", (r.width, r.height), "white")

    cap = ScreenCapture(region, grabber=fake_grabber)
    img = cap.grab()

    assert img.size == (30, 40)
    assert seen["region"] is region
    assert cap.region == region


def test_grab_resizes_when_scale_is_not_one():
    region = CaptureRegion(left=0, top=0, width=30, height=40)
    seen = {}

    def fake_grabber(r):
        seen["region"] = r
        # 模拟 mss 返回物理像素（2x）
        return Image.new("RGB", (r.width, r.height), "white")

    cap = ScreenCapture(region, grabber=fake_grabber, scale=2.0)
    img = cap.grab()

    # 图像归一化到逻辑尺寸
    assert img.size == (30, 40)
    # grabber 收到的是 ×2 的 mss 坐标
    assert seen["region"].width == 60
    assert seen["region"].height == 80
    assert seen["region"].left == 0
    assert seen["region"].top == 0
