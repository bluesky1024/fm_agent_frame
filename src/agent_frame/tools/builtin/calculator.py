"""内置工具：安全计算器。

用 ast 白名单解析表达式，而不是 eval，避免 LLM 传入的字符串被注入执行任意代码。
"""

from __future__ import annotations

import ast
import operator
from typing import Any, ClassVar

_BIN_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY_OPS: dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class CalculatorTool:
    name: ClassVar[str] = "calculator"
    description: ClassVar[str] = (
        "计算一个数学表达式，如 '2 + 3 * 4'。支持 + - * / % ** 和括号。"
    )
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "要计算的数学表达式"},
        },
        "required": ["expression"],
    }

    async def run(self, expression: str) -> str:
        try:
            node = ast.parse(expression, mode="eval")
            return str(self._eval(node.body))
        except Exception as exc:  # noqa: BLE001 - 把解析/计算错误作为文本返回
            return f"计算失败: {exc}"

    def _eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return self._eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](self._eval(node.left), self._eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](self._eval(node.operand))
        raise ValueError(f"不支持的表达式节点: {type(node).__name__}")
