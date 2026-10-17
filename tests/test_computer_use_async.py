"""计算机使用：同步截屏/标注通过 to_thread 隔离，不阻塞事件循环。"""

import asyncio
import time

from apps.minesweeper.board import BoardGeometry
from PIL import Image

from agent_frame.capabilities.computer_use import (
    CaptureRegion,
    GridAnnotator,
    ScreenCapture,
    ScreenObserver,
)


class SlowBackend:
    def grab(self, region: CaptureRegion) -> Image.Image:
        time.sleep(0.1)
        return Image.new("RGB", (region.width, region.height), "white")


async def test_observe_does_not_block_event_loop() -> None:
    capture = ScreenCapture(
        CaptureRegion(left=0, top=0, width=40, height=40), backend=SlowBackend()
    )
    geometry = BoardGeometry(origin_x=0, origin_y=0, cell_w=8, cell_h=8, rows=3, cols=3)
    observer = ScreenObserver(capture, annotator=GridAnnotator(geometry))

    ticked = asyncio.Event()

    async def ticker() -> None:
        await asyncio.sleep(0.02)
        ticked.set()

    task = asyncio.create_task(ticker())
    observe_task = asyncio.create_task(observer.observe())
    await asyncio.wait_for(ticked.wait(), timeout=1.0)

    assert not observe_task.done()  # 截屏仍在后台线程执行
    message = await observe_task
    await task

    assert message.role == "user"
    assert isinstance(message.content, list)
    assert message.content[1].image_url["url"].startswith("data:image/png;base64,")
