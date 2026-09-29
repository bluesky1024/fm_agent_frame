import logging

from agent_frame.obs import setup_logging


def test_setup_logging_writes_to_log_dir(tmp_path):
    root = logging.getLogger()
    orig_handlers = root.handlers[:]
    orig_level = root.level

    setup_logging(log_level="DEBUG", log_dir=str(tmp_path / "log"))
    new_handlers = [h for h in root.handlers if h not in orig_handlers]

    try:
        logging.getLogger("agent_frame.llm").debug("测试日志内容")
        for handler in new_handlers:
            handler.flush()

        log_file = tmp_path / "log" / "agent.log"
        assert log_file.exists()
        assert "测试日志内容" in log_file.read_text(encoding="utf-8")
    finally:
        for handler in new_handlers:
            handler.close()
        root.handlers[:] = orig_handlers
        root.setLevel(orig_level)
