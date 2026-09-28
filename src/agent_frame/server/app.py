"""HTTP 服务（打桩 / 预留）。

后续用 FastAPI 把 Agent 暴露成 HTTP 接口，供 Vue / React 前台调用。
当前仅打桩，不引入 fastapi 依赖，保证包在未安装 fastapi 时也能正常 import。
"""

from __future__ import annotations


def create_app() -> None:
    """预留：返回 FastAPI 应用实例。"""
    raise NotImplementedError("server 模块尚未实现，后续接入 FastAPI")
