"""统一异常体系。

所有框架内部抛出的异常都继承自 AgentFrameError，方便上层统一捕获。
错误分层（architecture.md §8）：
- ConfigError：配置缺失或非法
- LLMError：供应商调用失败；retryable 表示是否值得重试
- ToolError：工具注册、查找或执行失败；recoverable 表示可回填给模型
- GuardrailViolation：护栏拦截
- StepLimitExceeded：超过最大步数
- Cancelled：运行被取消
"""

from __future__ import annotations


class AgentFrameError(Exception):
    """框架所有异常的基类。"""


class ConfigError(AgentFrameError):
    """配置缺失或非法（如缺少 API key）。"""


class LLMError(AgentFrameError):
    """LLM 调用失败（网络、超时、限流、返回格式异常等）。"""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ToolError(AgentFrameError):
    """工具注册、查找或执行相关错误。"""

    def __init__(self, message: str, *, recoverable: bool = False) -> None:
        super().__init__(message)
        self.recoverable = recoverable


class AgentLoopError(AgentFrameError):
    """Agent 循环异常（如超过最大步数仍无法收敛）。"""


class StepLimitExceeded(AgentLoopError):
    """超过最大步数。"""


class GuardrailViolation(AgentFrameError):
    """护栏拦截了输入或输出。"""


class Cancelled(AgentFrameError):
    """运行被调用方取消。"""
