import base64
import io

from PIL import Image

from games.minesweeper import (
    CELL,
    COLS,
    GAME_ORIGIN_X,
    GAME_ORIGIN_Y,
    HEADER,
    LABEL_MARGIN_X,
    LABEL_MARGIN_Y,
    ROWS,
    MinesweeperBoard,
    board_config,
)


def test_first_reveal_never_hits_mine():
    b = MinesweeperBoard(rows=9, cols=9, n_mines=10)
    b.reveal(0, 0)
    assert b.status != "lost"
    assert not b.is_mine(0, 0)
    assert b.is_revealed(0, 0)


def test_reveal_mine_loses():
    b = MinesweeperBoard(rows=3, cols=3, n_mines=1, mines={(1, 1)})
    b.reveal(1, 1)
    assert b.status == "lost"


def test_blank_flood_fill_wins():
    b = MinesweeperBoard(rows=3, cols=3, n_mines=1, mines={(2, 2)})
    b.reveal(0, 0)
    assert b.status == "won"
    assert b.is_revealed(0, 1)
    assert b.is_revealed(2, 0)


def test_toggle_flag():
    b = MinesweeperBoard(rows=3, cols=3, n_mines=1, mines={(1, 1)})
    b.toggle_flag(0, 0)
    assert b.is_flagged(0, 0)
    b.toggle_flag(0, 0)
    assert not b.is_flagged(0, 0)


def test_flagged_cell_cannot_reveal():
    b = MinesweeperBoard(rows=3, cols=3, n_mines=1, mines={(1, 1)})
    b.toggle_flag(1, 1)
    b.reveal(1, 1)
    assert not b.is_revealed(1, 1)
    assert b.status == "playing"


def test_adjacent_mines_counts():
    b = MinesweeperBoard(rows=3, cols=3, n_mines=1, mines={(0, 0)})
    assert b.adjacent_mines(1, 1) == 1
    assert b.adjacent_mines(2, 2) == 0


def test_board_config_geometry():
    cfg = board_config()
    assert cfg["geometry"]["origin_x"] == GAME_ORIGIN_X
    assert cfg["geometry"]["origin_y"] == GAME_ORIGIN_Y + HEADER
    assert cfg["geometry"]["cell_w"] == CELL
    assert cfg["geometry"]["cell_h"] == CELL
    assert cfg["geometry"]["rows"] == ROWS
    assert cfg["geometry"]["cols"] == COLS


def test_board_config_region_includes_label_margin():
    cfg = board_config()
    ox, oy = GAME_ORIGIN_X, GAME_ORIGIN_Y + HEADER
    # 区域要向左/上各留出边距，行列标尺才画得进图内
    assert cfg["region"]["left"] == ox - LABEL_MARGIN_X
    assert cfg["region"]["top"] == oy - LABEL_MARGIN_Y
    assert cfg["region"]["width"] == COLS * CELL + LABEL_MARGIN_X
    assert cfg["region"]["height"] == ROWS * CELL + LABEL_MARGIN_Y
    assert cfg["restart"]["type"] == "click"
    assert cfg["restart"]["x"] == GAME_ORIGIN_X + COLS * CELL // 2
    assert cfg["restart"]["y"] == GAME_ORIGIN_Y + HEADER // 2


async def test_annotated_frame_contains_row_col_labels():
    from agent_frame.desktop.geometry import BoardGeometry
    from agent_frame.desktop.observer import BoardObserver
    from agent_frame.desktop.screen import CaptureRegion, ScreenCapture

    cfg = board_config()
    geo = BoardGeometry(**cfg["geometry"])
    cap = ScreenCapture(
        CaptureRegion(**cfg["region"]),
        grabber=lambda r: Image.new("RGB", (r.width, r.height), "white"),
    )
    msg = await BoardObserver(cap, geo).observe()

    data_url = msg.content[1].image_url["url"]
    png = base64.b64decode(data_url.split(",", 1)[1])
    img = Image.open(io.BytesIO(png)).convert("RGB")
    # 蓝色行列标尺应出现在图内（抗锯齿，用偏蓝判据）
    bluish = sum(
        1 for (r, g, b) in img.getdata() if b > 80 and b > r + 30 and b > g + 30
    )
    assert bluish > 0
