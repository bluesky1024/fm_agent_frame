"""日志配置：同时输出到控制台与 log/ 目录下的文件。"""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_dir: str = "log") -> None:
    """初始化日志系统：控制台 + 文件双输出。

    - log_level: 日志级别（DEBUG / INFO / WARNING ...），大小写不敏感
    - log_dir:   文件输出目录，日志写到 <log_dir>/agent.log
    """
    level = log_level.upper()
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(name)s: %(message)s"
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.FileHandler(log_dir_path / "agent.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
