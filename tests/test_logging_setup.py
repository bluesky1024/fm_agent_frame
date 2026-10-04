import logging

from agent_frame.obs import setup_logging


def test_setup_logging_separates_llm_logs(tmp_path):
    root = logging.getLogger()
    llm_logger = logging.getLogger("agent_frame.llm")

    # 保存原始状态，测后恢复，避免污染其他测试
    orig_root_handlers = root.handlers[:]
    orig_root_level = root.level
    orig_llm_handlers = llm_logger.handlers[:]
    orig_llm_level = llm_logger.level
    orig_llm_propagate = llm_logger.propagate

    setup_logging(log_level="DEBUG", log_dir=str(tmp_path / "log"))

    try:
        llm_logger.debug("LLM 专用内容")
        logging.getLogger("agent_frame.agent").debug("普通内容")

        for handler in root.handlers + llm_logger.handlers:
            handler.flush()

        llm_file = tmp_path / "log" / "llm.log"
        agent_file = tmp_path / "log" / "agent.log"
        assert llm_file.exists()
        assert agent_file.exists()

        llm_content = llm_file.read_text(encoding="utf-8")
        agent_content = agent_file.read_text(encoding="utf-8")

        # 专用日志只含 LLM 内容，不含别的
        assert "LLM 专用内容" in llm_content
        assert "普通内容" not in llm_content
        # 主日志只含普通内容，不含 LLM
        assert "普通内容" in agent_content
        assert "LLM 专用内容" not in agent_content
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers[:] = orig_root_handlers
        root.setLevel(orig_root_level)

        for handler in llm_logger.handlers:
            handler.close()
        llm_logger.handlers[:] = orig_llm_handlers
        llm_logger.setLevel(orig_llm_level)
        llm_logger.propagate = orig_llm_propagate
