"""多 Agent 能力：顺序编排实现；并行与交接仅协议。"""

from agent_frame.capabilities.multi_agent.base import (
    AgentHandoff,
    AgentOrchestrator,
    AgentTrace,
    OrchestrationResult,
    ParallelOrchestrator,
    SubAgentSpec,
    SubTask,
    TaskDecomposer,
)
from agent_frame.capabilities.multi_agent.orchestrator import AgentRunner, SequentialOrchestrator

__all__ = [
    "AgentHandoff",
    "AgentOrchestrator",
    "AgentRunner",
    "AgentTrace",
    "OrchestrationResult",
    "ParallelOrchestrator",
    "SequentialOrchestrator",
    "SubAgentSpec",
    "SubTask",
    "TaskDecomposer",
]
