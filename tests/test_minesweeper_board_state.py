"""从截图像素识别棋盘状态：已翻开 / 未翻开 / 插旗 / 踩雷。"""

from apps.minesweeper.board import BoardGeometry
from apps.minesweeper.board_state import COVERED, FLAGGED, REVEALED, analyze_board
from PIL import Image, ImageDraw

from agent_frame.capabilities.computer_use.annotate import GridAnnotator

_GEO = BoardGeometry(origin_x=0, origin_y=0, cell_w=10, cell_h=10, rows=9, cols=9)
_SIZE = (110, 110)


def _render(
    cells: dict[tuple[int, int], str],
    *,
    exploded: tuple[int, int] | None = None,
    flagged_with_red: tuple[int, int] | None = None,
    annotate: bool = False,
) -> Image.Image:
    img = Image.new("RGB", _SIZE, COVERED)
    draw = ImageDraw.Draw(img)
    fills = {"revealed": REVEALED, "covered": COVERED, "flagged": FLAGGED}
    for (row, col), kind in cells.items():
        x0, y0 = (col - 1) * 10, (row - 1) * 10
        draw.rectangle([x0, y0, x0 + 9, y0 + 9], fill=fills[kind])
    for point in (exploded, flagged_with_red):
        if point is None:
            continue
        row, col = point
        x0, y0 = (col - 1) * 10, (row - 1) * 10
        draw.line([x0 + 3, y0 + 3, x0 + 6, y0 + 6], fill=(204, 0, 0), width=1)
        draw.line([x0 + 3, y0 + 6, x0 + 6, y0 + 3], fill=(204, 0, 0), width=1)
    if annotate:
        img = GridAnnotator(_GEO).draw(img)
    return img


def _winning_cells() -> dict[tuple[int, int], str]:
    flagged = {(1, 1), (1, 2), (1, 3)}
    cells = {
        (row, col): "flagged" if (row, col) in flagged else "revealed"
        for row in range(1, 10)
        for col in range(1, 10)
    }
    return cells


def test_all_covered_is_playing():
    state = analyze_board(_render({}), _GEO)

    assert state.revealed == 0
    assert state.covered == 81
    assert state.flagged == 0
    assert state.is_won(3) is False
    assert state.is_lost() is False


def test_winning_board_has_all_safe_cells_revealed():
    state = analyze_board(_render(_winning_cells()), _GEO)

    assert state.revealed == 78
    assert state.flagged == 3
    assert state.is_won(3) is True
    assert state.is_lost() is False


def test_one_safe_cell_left_is_not_a_win():
    cells = _winning_cells()
    cells[(5, 5)] = "covered"

    state = analyze_board(_render(cells), _GEO)

    assert state.revealed == 77
    assert state.covered == 1
    assert state.is_won(3) is False


def test_revealed_mine_with_red_marker_is_lost():
    cells = _winning_cells()
    cells[(5, 5)] = "revealed"

    state = analyze_board(_render(cells, exploded=(5, 5)), _GEO)

    assert state.is_lost() is True
    assert state.is_won(3) is False


def test_single_red_pixel_is_not_an_explosion():
    img = _render(_winning_cells())
    x, y = (5 - 1) * 10 + 5, (5 - 1) * 10 + 5
    img.putpixel((x, y), (204, 0, 0))

    state = analyze_board(img, _GEO)

    assert state.is_lost() is False


def test_red_flag_glyph_is_not_an_explosion():
    cells = _winning_cells()

    state = analyze_board(_render(cells, flagged_with_red=(1, 1)), _GEO)

    assert state.is_lost() is False


def test_analyzer_ignores_annotation_grid_lines():
    state = analyze_board(_render(_winning_cells(), annotate=True), _GEO)

    assert state.revealed == 78
    assert state.is_won(3) is True


def test_unknown_colors_never_count_as_a_win():
    state = analyze_board(Image.new("RGB", _SIZE, "white"), _GEO)

    assert state.unknown == 81
    assert state.is_won(3) is False
