"""统一异常体系。

所有框架内部抛出的异常都继承自 AgentFrameError，方便上层统一捕获。
"""

from __future__ import annotations


class AgentFrameError(Exception):
    """框架所有异常的基类。"""


class ConfigError(AgentFrameError):
    """配置缺失或非法（如缺少 API key）。"""


class LLMError(AgentFrameError):
    """LLM 调用失败（网络、超时、限流、返回格式异常等）。"""


class ToolError(AgentFrameError):
    """工具注册、查找或执行相关错误。"""


class AgentLoopError(AgentFrameError):
    """Agent 循环异常（如超过最大步数仍无法收敛）。"""
