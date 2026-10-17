from PIL import Image

from agent_frame.capabilities.computer_use.screen import CaptureRegion, ScreenCapture


class FakeScreenBackend:
    def __init__(self) -> None:
        self.regions: list[CaptureRegion] = []

    def grab(self, region: CaptureRegion) -> Image.Image:
        self.regions.append(region)
        return Image.new("RGB", (region.width, region.height), "white")


def test_grab_delegates_to_backend_with_region():
    region = CaptureRegion(left=10, top=20, width=30, height=40)
    backend = FakeScreenBackend()

    cap = ScreenCapture(region, backend=backend)
    img = cap.grab()

    assert img.size == (30, 40)
    assert backend.regions == [region]
    assert cap.region == region


def test_grab_resizes_when_scale_is_not_one():
    region = CaptureRegion(left=0, top=0, width=30, height=40)
    backend = FakeScreenBackend()

    cap = ScreenCapture(region, backend=backend, scale=2.0)
    img = cap.grab()

    assert img.size == (30, 40)
    assert backend.regions[0].width == 60
    assert backend.regions[0].height == 80
    assert backend.regions[0].left == 0
    assert backend.regions[0].top == 0


def test_grab_derives_scaled_width_from_edges():
    region = CaptureRegion(left=0, top=0, width=13, height=13)
    backend = FakeScreenBackend()

    cap = ScreenCapture(region, backend=backend, scale=1.5)
    img = cap.grab()

    # 13 * 1.5 = 19.5；正确是 round(19.5)=20
    assert backend.regions[0].width == 20
    assert backend.regions[0].height == 20
    assert img.size == (13, 13)
