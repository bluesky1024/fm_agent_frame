"""配置加载：pydantic-settings，API key 等走环境变量或 .env 文件。"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。字段名自动映射为环境变量（大小写不敏感）。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # DeepSeek（OpenAI 兼容）
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"

    # Agent 循环
    max_steps: int = 8
    # 单次工具调用超时（秒）
    tool_timeout: float = 30.0
    # 上下文 token 预算与摘要滑窗保留的最近消息数
    context_token_budget: int = 4000
    compaction_keep_last: int = 6

    # LLM 调用
    request_timeout: float = 60.0
    max_retries: int = 2

    # 日志（对应环境变量 LOG_LEVEL，如 DEBUG / INFO / WARNING）
    log_level: str = "DEBUG"
    # 日志输出目录：文件写到 <log_dir>/agent.log
    log_dir: str = "log"
    # 是否在终端（控制台）打印日志
    log_console: bool = False


@lru_cache
def get_settings() -> Settings:
    """返回全局共享的配置实例（进程内只加载一次）。"""
    return Settings()
