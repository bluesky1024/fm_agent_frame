import logging

import pytest

from agent_frame.obs import setup_logging


@pytest.fixture
def restore_logging():
    """快照并恢复 root 与 agent_frame.llm 的日志状态，避免测试间污染。"""
    root = logging.getLogger()
    llm_logger = logging.getLogger("agent_frame.llm")

    root_handlers = root.handlers[:]
    root_level = root.level
    llm_handlers = llm_logger.handlers[:]
    llm_level = llm_logger.level
    llm_propagate = llm_logger.propagate

    yield

    for handler in root.handlers:
        handler.close()
    root.handlers[:] = root_handlers
    root.setLevel(root_level)

    for handler in llm_logger.handlers:
        handler.close()
    llm_logger.handlers[:] = llm_handlers
    llm_logger.setLevel(llm_level)
    llm_logger.propagate = llm_propagate


def test_setup_logging_separates_llm_logs(tmp_path, restore_logging):
    setup_logging(log_level="DEBUG", log_dir=str(tmp_path / "log"))

    llm_logger = logging.getLogger("agent_frame.llm")
    llm_logger.debug("LLM 专用内容")
    logging.getLogger("agent_frame.agent").debug("普通内容")

    for handler in logging.getLogger().handlers + llm_logger.handlers:
        handler.flush()

    llm_file = tmp_path / "log" / "llm.log"
    agent_file = tmp_path / "log" / "agent.log"
    assert llm_file.exists()
    assert agent_file.exists()

    llm_content = llm_file.read_text(encoding="utf-8")
    agent_content = agent_file.read_text(encoding="utf-8")

    assert "LLM 专用内容" in llm_content
    assert "普通内容" not in llm_content
    assert "普通内容" in agent_content
    assert "LLM 专用内容" not in agent_content


def test_llm_log_always_records_debug_regardless_of_level(tmp_path, restore_logging):
    # LOG_LEVEL=INFO 时，LLM 专用日志仍应完整记录（不受级别门控）
    setup_logging(log_level="INFO", log_dir=str(tmp_path / "log"), console=False)

    logging.getLogger("agent_frame.llm").debug("LLM 始终记录")
    for handler in logging.getLogger("agent_frame.llm").handlers:
        handler.flush()

    llm_content = (tmp_path / "log" / "llm.log").read_text(encoding="utf-8")
    assert "LLM 始终记录" in llm_content


def test_setup_logging_can_disable_console(tmp_path, restore_logging):
    setup_logging(log_level="INFO", log_dir=str(tmp_path / "log"), console=False)

    root = logging.getLogger()
    # console=False 时，root 不应有直接写 stderr 的 StreamHandler
    # （注意 FileHandler 是 StreamHandler 的子类，需用 type() 精确判断）
    assert not any(type(h) is logging.StreamHandler for h in root.handlers)
