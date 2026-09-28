import pytest

from agent_frame.tools import ToolRegistry
from agent_frame.tools.builtin import CalculatorTool, CurrentTimeTool


async def test_calculator():
    tool = CalculatorTool()
    assert await tool.run(expression="2 + 3 * 4") == "14"


async def test_calculator_rejects_injection():
    tool = CalculatorTool()
    out = await tool.run(expression="__import__('os').system('ls')")
    assert out.startswith("计算失败")


async def test_current_time():
    tool = CurrentTimeTool()
    out = await tool.run()
    assert "T" in out  # ISO 格式


def test_registry_roundtrip():
    reg = ToolRegistry([CalculatorTool()])
    assert reg.names() == ["calculator"]
    assert reg.get("calculator").name == "calculator"


def test_registry_duplicate_raises():
    reg = ToolRegistry([CalculatorTool()])
    with pytest.raises(Exception):
        reg.register(CalculatorTool())
