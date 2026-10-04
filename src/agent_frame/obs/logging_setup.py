"""日志配置：控制台 + 主日志文件 + 独立的 LLM 交互日志。"""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_dir: str = "log") -> None:
    """初始化日志系统，输出分三路。

    - log_level: 日志级别（DEBUG / INFO / WARNING ...），大小写不敏感
    - log_dir:   文件输出目录，默认 "log"

    1. 控制台：主日志（不含 LLM 交互）
    2. <log_dir>/agent.log：主日志（不含 LLM 交互）
    3. <log_dir>/llm.log：仅 LLM 请求 / 回包（原始 JSON）
    """
    level = log_level.upper()
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(name)s: %(message)s"
    )

    # 根 logger：控制台 + 主日志文件
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.FileHandler(log_dir_path / "agent.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # LLM 交互 logger：独立文件，不冒泡到根 logger（避免混入主日志）
    llm_logger = logging.getLogger("agent_frame.llm")
    llm_logger.setLevel(level)
    llm_logger.propagate = False
    llm_logger.handlers.clear()

    llm_handler = logging.FileHandler(log_dir_path / "llm.log", encoding="utf-8")
    llm_handler.setLevel(level)
    llm_handler.setFormatter(formatter)
    llm_logger.addHandler(llm_handler)
