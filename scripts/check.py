"""运行本仓库的全部本地检查：lint、format、类型、依赖方向与测试。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lint_imports_command() -> list[str]:
    """返回跨平台的 lint-imports 调用命令。"""
    executable = shutil.which("lint-imports")
    if executable:
        return [executable]

    scripts_dir = Path(sys.executable).parent / ("Scripts" if os.name == "nt" else "bin")
    for name in ("lint-imports.exe", "lint-imports"):
        candidate = scripts_dir / name
        if candidate.exists():
            return [str(candidate)]

    return [sys.executable, "-m", "importlinter.cli"]


def run_check(label: str, command: list[str]) -> None:
    print(f"\n==> {label}", flush=True)
    print("    " + " ".join(command), flush=True)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(command, cwd=ROOT, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    run_check("ruff lint", [sys.executable, "-m", "ruff", "check", "."])
    run_check("ruff format", [sys.executable, "-m", "ruff", "format", "--check", "."])
    run_check("mypy", [sys.executable, "-m", "mypy"])
    run_check("import-linter", lint_imports_command())
    run_check("pytest", [sys.executable, "-m", "pytest", "-q"])
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
