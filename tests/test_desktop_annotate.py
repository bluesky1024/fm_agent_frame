from PIL import Image

from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry


def _geo() -> BoardGeometry:
    return BoardGeometry(origin_x=10, origin_y=10, cell_w=8, cell_h=8, rows=3, cols=3)


def test_draw_preserves_size_and_mode():
    img = Image.new("RGB", (60, 60), "white")
    out = GridAnnotator(_geo()).draw(img)
    assert out.size == (60, 60)
    assert out.mode == "RGB"


def test_draw_modifies_pixels_inside_grid():
    img = Image.new("RGB", (60, 60), "white")
    out = GridAnnotator(_geo()).draw(img)
    # 网格线画在 x=10 处，应出现非白像素
    assert out.getpixel((10, 10)) != (255, 255, 255)


def test_draw_does_not_mutate_input():
    img = Image.new("RGB", (60, 60), "white")
    GridAnnotator(_geo()).draw(img)
    assert img.getpixel((10, 10)) == (255, 255, 255)
