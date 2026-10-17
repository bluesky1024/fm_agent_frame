"""一局结束结论：模型必须输出的固定文本。"""

from __future__ import annotations

import re

CONCLUSION_WON = "本局结束：胜利"
CONCLUSION_LOST = "本局结束：失败"

# 模型常把提示词里的判据括号一起抄下来，因此只要求行首命中固定串；
# 真假胜负最终由应用层读截图校验（run_autoplay）。
_CONCLUSION = re.compile(r"^\s*(本局结束：(?:胜利|失败))", re.MULTILINE)


def parse_conclusion(text: str) -> str | None:
    """返回命中的固定结论串；未命中返回 None。"""
    match = _CONCLUSION.search(text)
    return match.group(1) if match else None
