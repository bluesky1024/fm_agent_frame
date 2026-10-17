"""AgentService：把 runtime 暴露给 HTTP / 其他接口层。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from agent_frame.core.events import AgentEvent
from agent_frame.interfaces.server.models import (
    ChatRequest,
    ChatResponse,
    InvalidRequestError,
)
from agent_frame.interfaces.session import InMemorySession, SessionManager
from agent_frame.runtime.runtime import AgentRuntime
from agent_frame.runtime.spec import AgentSpec


class AgentService:
    """单 Agent 服务：对话、流式事件与会话管理。"""

    def __init__(
        self,
        runtime: AgentRuntime,
        spec: AgentSpec,
        sessions: SessionManager | None = None,
    ) -> None:
        self._runtime = runtime
        self._spec = spec
        self._sessions = sessions or SessionManager()

    @property
    def sessions(self) -> SessionManager:
        return self._sessions

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self._validate(request)
        session = self._sessions.get_or_create(request.session_id)
        result = await self._runtime.run_collect(self._spec, session, request.message)
        return ChatResponse(
            reply=result.output,
            session_id=session.id,
            usage=result.usage.model_dump(),
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[AgentEvent]:
        self._validate(request)
        session = self._sessions.get_or_create(request.session_id)
        async for event in self._runtime.run(self._spec, session, request.message):
            yield event

    def _validate(self, request: ChatRequest) -> None:
        if not request.message.strip():
            raise InvalidRequestError("message 不能为空")

    def get_session(self, session_id: str) -> InMemorySession | None:
        return self._sessions.get(session_id)
