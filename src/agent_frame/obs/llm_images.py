"""把 LLM 请求里的内联图片（base64 data URL）抽出落盘，便于日志阅读。

多模态请求的图片是内联 base64，直接写进日志会让文件爆大且无法查看。
本模块把 data URL 解码存成 PNG（按内容哈希命名、天然去重），并把日志里的
url 替换成文件路径，从而日志只留一个可点击的引用。
"""

from __future__ import annotations

import base64
import copy
import hashlib
from pathlib import Path

_DATA_PREFIX = "data:image/png;base64,"


def save_images_and_strip(messages: list[dict], pic_dir: Path) -> list[dict]:
    """把 messages 里 image_url 的 data URL 存成 PNG，url 替换为文件路径。

    - 深拷贝入参，不修改原始请求。
    - 图片按内容哈希命名（<sha1[:12]>.png），相同图片只落盘一次。
    - 无图片时不创建 pic_dir，原样返回。
    """
    out = copy.deepcopy(messages)
    for message in out:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                continue
            image_url = part.get("image_url")
            if not isinstance(image_url, dict):
                continue
            url = image_url.get("url")
            if not isinstance(url, str) or not url.startswith(_DATA_PREFIX):
                continue
            png = base64.b64decode(url[len(_DATA_PREFIX):])
            path = Path(pic_dir) / f"{hashlib.sha1(png).hexdigest()[:12]}.png"
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png)
            image_url["url"] = str(path)
    return out
