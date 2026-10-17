"""最小 HTTP 服务：单聊天端点 + SSE，多会话由 SessionManager 隔离。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from agent_frame.interfaces.server.models import (
    ChatRequest,
    ErrorDetail,
    ErrorResponse,
    InvalidRequestError,
)
from agent_frame.interfaces.server.service import AgentService


def create_app(service: AgentService) -> FastAPI:
    """构造 FastAPI 应用；调用方负责组装 runtime/spec/service。"""
    app = FastAPI(title="agent-frame", version="0.1.0")

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {"msg": "请求参数非法", "loc": []}
        message = str(first.get("msg", "请求参数非法"))
        payload = ErrorResponse(error=ErrorDetail(type="validation_error", message=message))
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.post("/chat")
    async def chat(request: ChatRequest):
        try:
            if request.stream:
                return StreamingResponse(
                    _sse_events(service, request),
                    media_type="text/event-stream",
                )
            return await service.chat(request)
        except InvalidRequestError as exc:
            payload = ErrorResponse(error=ErrorDetail(type="invalid_request", message=str(exc)))
            return JSONResponse(status_code=422, content=payload.model_dump())

    return app


async def _sse_events(service: AgentService, request: ChatRequest) -> AsyncIterator[str]:
    async for event in service.stream(request):
        yield f"data: {event.model_dump_json()}\n\n"
