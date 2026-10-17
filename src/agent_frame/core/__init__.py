"""核心层：消息、事件、错误、配置与共享类型。

本层不依赖任何内部模块；其余各层只从 ``agent_frame.core`` 导入这些基础类型。
"""

from agent_frame.core.config import Settings, get_settings
from agent_frame.core.errors import (
    AgentFrameError,
    AgentLoopError,
    Cancelled,
    ConfigError,
    GuardrailViolation,
    LLMError,
    StepLimitExceeded,
    ToolError,
)
from agent_frame.core.events import (
    AgentEvent,
    ContextBuilt,
    Error,
    LLMCompleted,
    LLMDelta,
    RunEnd,
    RunStart,
    StepStart,
    ToolCallRequested,
    ToolResult,
)
from agent_frame.core.messages import ContentPart, ImagePart, Message, TextPart, ToolCall
from agent_frame.core.types import AgentResult, TokenUsage, ToolSpec

__all__ = [
    "AgentEvent",
    "AgentFrameError",
    "AgentLoopError",
    "AgentResult",
    "Cancelled",
    "ConfigError",
    "ContentPart",
    "ContextBuilt",
    "Error",
    "GuardrailViolation",
    "ImagePart",
    "LLMCompleted",
    "LLMDelta",
    "LLMError",
    "Message",
    "RunEnd",
    "RunStart",
    "Settings",
    "StepLimitExceeded",
    "StepStart",
    "TextPart",
    "TokenUsage",
    "ToolCall",
    "ToolCallRequested",
    "ToolError",
    "ToolResult",
    "ToolSpec",
    "get_settings",
]
