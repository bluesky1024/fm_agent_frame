from agent_frame.desktop.mouse import MouseController, enable_dpi_awareness


class FakeBackend:
    """签名模拟真实 pyautogui.click：第 3 个位置参数是 clicks，不是 button。

    这样能抓到「把 button 按位置传参」的错误（真实 pyautogui 会把它当成 clicks）。
    events 按调用顺序记录所有操作，用于验证 shift_click 的按下/点击/释放顺序。
    """

    def __init__(self) -> None:
        self.clicks = []
        self.moves = []
        self.presses = []
        self.events = []

    def click(
        self,
        x=None,
        y=None,
        clicks=1,
        interval=0.0,
        button="primary",
        duration=0.0,
        tween=None,
        logScreenshot=None,
        _pause=True,
    ):
        self.clicks.append((x, y, button))
        self.events.append(("click", x, y, button))

    def moveTo(self, x, y):
        self.moves.append((x, y))
        self.events.append(("moveTo", x, y))

    def press(self, key):
        self.presses.append(key)
        self.events.append(("press", key))

    def keyDown(self, key):
        self.events.append(("keyDown", key))

    def keyUp(self, key):
        self.events.append(("keyUp", key))


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


def test_shift_click_holds_shift_around_left_click():
    b = FakeBackend()
    MouseController(backend=b).shift_click(10, 20)
    assert b.events == [
        ("keyDown", "shift"),
        ("click", 10, 20, "left"),
        ("keyUp", "shift"),
    ]


def test_shift_click_releases_shift_even_if_click_raises():
    class BoomBackend(FakeBackend):
        def click(self, *a, **k):
            raise RuntimeError("boom")

    b = BoomBackend()
    try:
        MouseController(backend=b).shift_click(1, 2)
    except RuntimeError:
        pass
    assert b.events == [("keyDown", "shift"), ("keyUp", "shift")]


def test_enable_dpi_awareness_does_not_raise():
    enable_dpi_awareness()  # 非 Windows 平台为 no-op，不应抛异常
