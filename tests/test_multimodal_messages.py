import base64

from agent_frame.messages import Message


def test_user_with_image_builds_text_and_image_parts():
    png = b"\x89PNG\r\n\x1a\nfake"
    m = Message.user_with_image("这是棋盘", png, detail="high")

    assert m.role == "user"
    assert isinstance(m.content, list)
    text_part, image_part = m.content
    assert text_part.type == "text"
    assert text_part.text == "这是棋盘"
    assert image_part.type == "image_url"
    assert image_part.image_url["url"].startswith("data:image/png;base64,")
    payload = image_part.image_url["url"].split(",", 1)[1]
    assert base64.b64decode(payload) == png
    assert image_part.image_url["detail"] == "high"


def test_plain_text_content_still_works():
    m = Message.user("hi")
    assert m.content == "hi"


from agent_frame.llm.openai_compat import _to_openai_messages


def test_to_openai_messages_emits_multimodal_parts():
    m = Message.user_with_image("棋盘", b"\x89PNG", detail="high")
    out = _to_openai_messages([m])

    assert out[0]["role"] == "user"
    parts = out[0]["content"]
    assert parts[0] == {"type": "text", "text": "棋盘"}
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert parts[1]["image_url"]["detail"] == "high"


def test_to_openai_messages_keeps_text_as_string():
    out = _to_openai_messages([Message.user("hi")])
    assert out[0]["content"] == "hi"
