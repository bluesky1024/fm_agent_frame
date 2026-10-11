import pytest

from agent_frame.desktop.geometry import BoardGeometry


def _geo() -> BoardGeometry:
    return BoardGeometry(
        origin_x=100, origin_y=200, cell_w=20, cell_h=24, rows=9, cols=9
    )


def test_cell_center_is_one_based():
    g = _geo()
    assert g.cell_center(1, 1) == (110, 212)
    assert g.cell_center(2, 3) == (150, 236)


def test_cell_center_out_of_range_raises():
    g = _geo()
    with pytest.raises(ValueError):
        g.cell_center(10, 1)


def test_cell_center_zero_or_negative_raises():
    g = _geo()
    with pytest.raises(ValueError):
        g.cell_center(1, 0)


def test_translated_shifts_origin_only():
    g = _geo()
    moved = g.translated(-100, -200)
    assert moved.origin_x == 0
    assert moved.origin_y == 0
    assert moved.cell_center(1, 1) == (10, 12)
