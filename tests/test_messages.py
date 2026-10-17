from agent_frame.core.messages import Message, ToolCall


def test_system_message():
    m = Message.system("hello")
    assert m.role == "system"
    assert m.content == "hello"


def test_assistant_with_tool_calls():
    tc = ToolCall(id="1", name="calculator", arguments={"expression": "1+1"})
    m = Message.assistant(tool_calls=[tc])
    assert m.tool_calls[0].name == "calculator"


def test_message_dump_excludes_none():
    m = Message.user("hi")
    data = m.model_dump(exclude_none=True)
    assert "tool_calls" not in data
    assert "tool_call_id" not in data
