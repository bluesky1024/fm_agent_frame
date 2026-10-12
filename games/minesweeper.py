"""tkinter 扫雷游戏：被扫雷视觉 Agent 操作的目标程序。

游戏逻辑（MinesweeperBoard）与 GUI 分离，逻辑可独立单元测试。
GUI 是无边框固定大小窗口，棋盘坐标精确可算。
"""

from __future__ import annotations

import random
import tkinter as tk

CELL = 32
HEADER = 40
ROWS = 9
COLS = 9
MINES = 10
GAME_ORIGIN_X = 200
GAME_ORIGIN_Y = 200


class MinesweeperBoard:
    """扫雷棋盘纯逻辑（0 基行列）。不依赖任何 GUI。"""

    def __init__(
        self,
        rows: int = ROWS,
        cols: int = COLS,
        n_mines: int = MINES,
        *,
        mines: set[tuple[int, int]] | None = None,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.n_mines = n_mines
        if mines is not None:
            self._mines = set(mines)
            self._mines_placed = True
        else:
            self._mines: set[tuple[int, int]] = set()
            self._mines_placed = False
        self._revealed: set[tuple[int, int]] = set()
        self._flagged: set[tuple[int, int]] = set()
        self._status = "playing"

    @property
    def status(self) -> str:
        return self._status

    def reveal(self, row: int, col: int) -> None:
        """翻开格子；首次翻开时才布雷（保证首点及其周围安全）。"""
        if self._status != "playing":
            return
        if (row, col) in self._flagged:
            return
        if not self._mines_placed:
            self._place_mines(row, col)
        if (row, col) in self._mines:
            self._revealed.add((row, col))
            self._status = "lost"
            return
        self._flood_reveal(row, col)
        if len(self._revealed) == self.rows * self.cols - len(self._mines):
            self._status = "won"

    def toggle_flag(self, row: int, col: int) -> None:
        if self._status != "playing":
            return
        if (row, col) in self._revealed:
            return
        if (row, col) in self._flagged:
            self._flagged.remove((row, col))
        else:
            self._flagged.add((row, col))

    def adjacent_mines(self, row: int, col: int) -> int:
        return sum(
            1
            for dr in (-1, 0, 1)
            for dc in (-1, 0, 1)
            if (dr or dc)
            and 0 <= row + dr < self.rows
            and 0 <= col + dc < self.cols
            and (row + dr, col + dc) in self._mines
        )

    def is_revealed(self, row: int, col: int) -> bool:
        return (row, col) in self._revealed

    def is_flagged(self, row: int, col: int) -> bool:
        return (row, col) in self._flagged

    def is_mine(self, row: int, col: int) -> bool:
        return (row, col) in self._mines

    def _place_mines(self, safe_row: int, safe_col: int) -> None:
        forbidden = {(safe_row, safe_col)}
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                r, c = safe_row + dr, safe_col + dc
                if 0 <= r < self.rows and 0 <= c < self.cols:
                    forbidden.add((r, c))
        candidates = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if (r, c) not in forbidden
        ]
        self._mines = set(random.sample(candidates, self.n_mines))
        self._mines_placed = True

    def _flood_reveal(self, row: int, col: int) -> None:
        stack = [(row, col)]
        while stack:
            r, c = stack.pop()
            if (r, c) in self._revealed or (r, c) in self._flagged:
                continue
            if (r, c) in self._mines:
                continue
            self._revealed.add((r, c))
            if self.adjacent_mines(r, c) == 0:
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols:
                            if (nr, nc) not in self._revealed and (nr, nc) not in self._flagged:
                                stack.append((nr, nc))


class MinesweeperGUI:
    """tkinter 棋盘渲染 + 鼠标事件。棋盘左上角精确落在窗口 (0, HEADER)。"""

    def __init__(self, root: tk.Tk, board: MinesweeperBoard, origin_x: int = GAME_ORIGIN_X, origin_y: int = GAME_ORIGIN_Y) -> None:
        self.root = root
        self.board = board
        self.width = COLS * CELL
        self.height = HEADER + ROWS * CELL
        root.overrideredirect(True)  # 无边框，窗口内容从 (origin_x, origin_y) 精确开始
        root.geometry(f"{self.width}x{self.height}+{origin_x}+{origin_y}")
        self.canvas = tk.Canvas(root, width=self.width, height=self.height, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_left)
        self.canvas.bind("<Button-3>", self._on_right)
        self._draw()

    def _cell_rect(self, row: int, col: int) -> tuple[int, int, int, int]:
        x0 = col * CELL
        y0 = HEADER + row * CELL
        return x0, y0, x0 + CELL, y0 + CELL

    def _restart_rect(self) -> tuple[int, int, int, int]:
        cx = self.width // 2
        return cx - 16, 4, cx + 16, 36

    def _draw(self) -> None:
        self.canvas.delete("all")
        x0, y0, x1, y1 = self._restart_rect()
        self.canvas.create_rectangle(x0, y0, x1, y1, fill="#cccccc", outline="#888888")
        face = {"playing": "☺", "won": "😎", "lost": "😵"}[self.board.status]
        self.canvas.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=face, font=("Arial", 16))
        for r in range(self.board.rows):
            for c in range(self.board.cols):
                cx0, cy0, cx1, cy1 = self._cell_rect(r, c)
                if self.board.is_revealed(r, c):
                    self.canvas.create_rectangle(cx0, cy0, cx1, cy1, fill="#e0e0e0", outline="#888888")
                    if self.board.is_mine(r, c):
                        self.canvas.create_text((cx0 + cx1) // 2, (cy0 + cy1) // 2, text="*", font=("Arial", 16), fill="#cc0000")
                    else:
                        n = self.board.adjacent_mines(r, c)
                        if n > 0:
                            self.canvas.create_text((cx0 + cx1) // 2, (cy0 + cy1) // 2, text=str(n), font=("Arial", 14))
                elif self.board.is_flagged(r, c):
                    self.canvas.create_rectangle(cx0, cy0, cx1, cy1, fill="#cccccc", outline="#888888")
                    self.canvas.create_text((cx0 + cx1) // 2, (cy0 + cy1) // 2, text="🚩", font=("Arial", 12))
                else:
                    self.canvas.create_rectangle(cx0, cy0, cx1, cy1, fill="#bbbbbb", outline="#888888")

    def _on_left(self, event: tk.Event) -> None:
        if self._in_restart(event.x, event.y):
            self.board = MinesweeperBoard(ROWS, COLS, MINES)
            self._draw()
            return
        col = event.x // CELL
        row = (event.y - HEADER) // CELL
        if 0 <= row < ROWS and 0 <= col < COLS:
            self.board.reveal(row, col)
            self._draw()

    def _on_right(self, event: tk.Event) -> None:
        col = event.x // CELL
        row = (event.y - HEADER) // CELL
        if 0 <= row < ROWS and 0 <= col < COLS:
            self.board.toggle_flag(row, col)
            self._draw()

    def _in_restart(self, x: int, y: int) -> bool:
        x0, y0, x1, y1 = self._restart_rect()
        return x0 <= x < x1 and y0 <= y < y1


def board_config() -> dict:
    """返回 agent config 所需的几何/区域/重开参数（屏幕绝对坐标，1 基）。

    棋盘左上角格子外沿在屏幕 (GAME_ORIGIN_X, GAME_ORIGIN_Y + HEADER)；
    重开按钮中心在屏幕 (GAME_ORIGIN_X + COLS*CELL//2, GAME_ORIGIN_Y + HEADER//2)。
    """
    ox = GAME_ORIGIN_X
    oy = GAME_ORIGIN_Y + HEADER
    return {
        "geometry": {
            "origin_x": ox,
            "origin_y": oy,
            "cell_w": CELL,
            "cell_h": CELL,
            "rows": ROWS,
            "cols": COLS,
        },
        "region": {"left": ox, "top": oy, "width": COLS * CELL, "height": ROWS * CELL},
        "restart": {
            "type": "click",
            "x": GAME_ORIGIN_X + COLS * CELL // 2,
            "y": GAME_ORIGIN_Y + HEADER // 2,
        },
    }


def main() -> None:
    root = tk.Tk()
    board = MinesweeperBoard(ROWS, COLS, MINES)
    MinesweeperGUI(root, board)
    root.mainloop()


if __name__ == "__main__":
    main()
