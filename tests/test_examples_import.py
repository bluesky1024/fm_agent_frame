"""示例可导入性：确保 01–03 使用当前 API 且没有旧模块引用。"""

import importlib.util
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.mark.parametrize("filename", ["01_hello_llm.py", "02_tool_agent.py", "03_interactive.py"])
def test_example_imports_and_has_main(filename: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(EXAMPLES))
    module_name = f"example_{filename.removesuffix('.py')}"
    module_spec = importlib.util.spec_from_file_location(module_name, EXAMPLES / filename)
    assert module_spec is not None and module_spec.loader is not None

    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_name] = module
    module_spec.loader.exec_module(module)

    assert callable(module.main)
