import importlib

import pytest

PACKAGES = [
    "agent_frame.core",
    "agent_frame.context",
    "agent_frame.runtime",
    "agent_frame.capabilities",
    "agent_frame.capabilities.retrieval",
    "agent_frame.capabilities.multi_agent",
    "agent_frame.capabilities.guardrails",
    "agent_frame.capabilities.hitl",
    "agent_frame.capabilities.mcp",
    "agent_frame.capabilities.sandbox",
    "agent_frame.capabilities.computer_use",
    "agent_frame.interfaces",
    "agent_frame.interfaces.server",
]


@pytest.mark.parametrize("package", PACKAGES)
def test_package_is_importable(package: str) -> None:
    assert importlib.import_module(package) is not None
