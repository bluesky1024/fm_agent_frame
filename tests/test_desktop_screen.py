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
