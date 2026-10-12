from agent_frame.desktop.mouse import MouseController, enable_dpi_awareness


class FakeBackend:
    def __init__(self) -> None:
        self.clicks = []
        self.moves = []
        self.presses = []

    def click(self, x, y, button):
        self.clicks.append((x, y, button))

    def moveTo(self, x, y):
        self.moves.append((x, y))

    def press(self, key):
        self.presses.append(key)


def test_click_forwards_to_backend():
    b = FakeBackend()
    m = MouseController(backend=b)
    m.click(10, 20)
    m.click(30, 40, button="right")
    assert b.clicks == [(10, 20, "left"), (30, 40, "right")]


def test_move_to_forwards_to_backend():
    b = FakeBackend()
    MouseController(backend=b).move_to(5, 6)
    assert b.moves == [(5, 6)]


def test_press_forwards_to_backend():
    b = FakeBackend()
    MouseController(backend=b).press("f2")
    assert b.presses == ["f2"]


def test_enable_dpi_awareness_does_not_raise():
    enable_dpi_awareness()  # 非 Windows 平台为 no-op，不应抛异常
