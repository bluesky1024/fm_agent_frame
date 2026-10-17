from apps.minesweeper.outcome import CONCLUSION_LOST, CONCLUSION_WON
from apps.minesweeper.prompt import build_system_prompt


def test_prompt_contains_mine_count_and_win_target():
    prompt = build_system_prompt(mines=3, total_cells=81)

    assert "本局共 3 颗雷" in prompt
    assert "已翻开 78 格才算胜利" in prompt


def test_prompt_contains_both_fixed_conclusions():
    prompt = build_system_prompt(mines=3, total_cells=81)

    assert CONCLUSION_WON in prompt
    assert CONCLUSION_LOST in prompt
