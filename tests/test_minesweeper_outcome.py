from apps.minesweeper.outcome import CONCLUSION_LOST, CONCLUSION_WON, parse_conclusion


def test_parse_conclusion_matches_exact_lines():
    assert parse_conclusion(CONCLUSION_WON) == CONCLUSION_WON
    assert parse_conclusion(CONCLUSION_LOST) == CONCLUSION_LOST


def test_parse_conclusion_finds_line_among_other_text():
    text = f"盘面已无未翻开格。\n{CONCLUSION_WON}\n"
    assert parse_conclusion(text) == CONCLUSION_WON


def test_parse_conclusion_tolerates_trailing_explanation():
    # 真实运行中模型会把提示词里的括号判据一起抄下来
    text = f"{CONCLUSION_WON}（所有非雷格都已翻开）"
    assert parse_conclusion(text) == CONCLUSION_WON


def test_parse_conclusion_ignores_mentions_inside_sentences():
    assert parse_conclusion("现在还不能确定是否胜利") is None
    assert parse_conclusion("距离本局结束：胜利还有很远") is None


def test_parse_conclusion_returns_none_when_absent():
    assert parse_conclusion("") is None
    assert parse_conclusion("请提供最新棋盘截图以便我继续判断。") is None
