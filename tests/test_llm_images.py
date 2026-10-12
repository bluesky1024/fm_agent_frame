import base64
import hashlib

from agent_frame.obs.llm_images import save_images_and_strip

PNG = b"\x89PNG\r\n\x1a\n" + b"fake-png-bytes"


def _data_url(png: bytes = PNG) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _image_message(png: bytes = PNG) -> dict:
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": "棋盘"},
            {"type": "image_url", "image_url": {"url": _data_url(png), "detail": "high"}},
        ],
    }


def _expected_name(png: bytes = PNG) -> str:
    return hashlib.sha1(png).hexdigest()[:12] + ".png"


def test_saves_png_and_replaces_url(tmp_path):
    pic_dir = tmp_path / "pic"
    out = save_images_and_strip([_image_message()], pic_dir)

    saved = pic_dir / _expected_name()
    assert saved.exists()
    assert saved.read_bytes() == PNG
    assert out[0]["content"][1]["image_url"]["url"] == str(saved)
    # detail 保持不变
    assert out[0]["content"][1]["image_url"]["detail"] == "high"


def test_text_parts_and_string_content_unchanged(tmp_path):
    messages = [
        {"role": "system", "content": "你是扫雷专家"},
        _image_message(),
    ]
    out = save_images_and_strip(messages, tmp_path / "pic")
    assert out[0]["content"] == "你是扫雷专家"
    assert out[1]["content"][0] == {"type": "text", "text": "棋盘"}


def test_same_image_deduped_to_one_file(tmp_path):
    pic_dir = tmp_path / "pic"
    out = save_images_and_strip(
        [_image_message(), _image_message()], pic_dir
    )
    files = list(pic_dir.glob("*.png"))
    assert len(files) == 1
    assert out[0]["content"][1]["image_url"]["url"] == out[1]["content"][1]["image_url"]["url"]


def test_different_images_saved_separately(tmp_path):
    pic_dir = tmp_path / "pic"
    other = b"\x89PNG\r\n\x1a\nother"
    out = save_images_and_strip(
        [_image_message(), _image_message(other)], pic_dir
    )
    assert len(list(pic_dir.glob("*.png"))) == 2
    assert out[0]["content"][1]["image_url"]["url"] != out[1]["content"][1]["image_url"]["url"]


def test_no_images_does_not_create_dir(tmp_path):
    pic_dir = tmp_path / "pic"
    messages = [{"role": "user", "content": "纯文本"}]
    out = save_images_and_strip(messages, pic_dir)
    assert not pic_dir.exists()
    assert out == messages


def test_does_not_mutate_input(tmp_path):
    original = _image_message()
    save_images_and_strip([original], tmp_path / "pic")
    assert original["content"][1]["image_url"]["url"] == _data_url()
