"""上下文层：每轮请求视图的装配与（后续）压缩。"""

from agent_frame.context.builder import BuiltContext, ContextBuilder
from agent_frame.context.compaction import compact_if_needed, history_view
from agent_frame.context.providers import ContextProvider, ContextRequest
from agent_frame.core.tokens import estimate_tokens

__all__ = [
    "BuiltContext",
    "ContextBuilder",
    "ContextProvider",
    "ContextRequest",
    "compact_if_needed",
    "estimate_tokens",
    "history_view",
]
