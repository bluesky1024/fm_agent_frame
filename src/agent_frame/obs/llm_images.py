"""把 LLM 请求里的内联图片（base64 data URL）抽出落盘，便于日志阅读。

多模态请求的图片是内联 base64，直接写进日志会让文件爆大且无法查看。
本模块把 data URL 解码存成 PNG，并把日志里的 url 替换成文件路径，
从而日志只留一个可点击的引用。

文件名形如 ``<时间戳>_<内容哈希>.png``：时间戳前缀便于按顺序查看，
哈希后缀用于按内容去重（messages 累积，同一截图会在后续请求中反复出现，
去重后每张唯一截图只落盘一次）。
"""

from __future__ import annotations

import base64
import copy
import hashlib
from datetime import datetime
from pathlib import Path

_DATA_PREFIX = "data:image/png;base64,"

# (pic_dir, 内容哈希) -> 已落盘的文件路径。跨调用去重，避免累积历史里
# 的重复截图被反复写盘（否则文件数会随步数呈 O(N^2) 增长）。
_saved: dict[tuple[str, str], str] = {}


def save_images_and_strip(messages: list[dict], pic_dir: Path) -> list[dict]:
    """把 messages 里 image_url 的 data URL 存成 PNG，url 替换为文件路径。

    - 深拷贝入参，不修改原始请求。
    - 文件名 ``<时间戳>_<sha1[:12]>.png``，相同图片只落盘一次。
    - 无图片时不创建 pic_dir，原样返回。
    """
    out = copy.deepcopy(messages)
    pic_dir = Path(pic_dir)
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
            digest = hashlib.sha1(png).hexdigest()[:12]
            key = (str(pic_dir), digest)
            if key not in _saved:
                path = pic_dir / f"{_timestamp()}_{digest}.png"
                pic_dir.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png)
                _saved[key] = str(path)
            image_url["url"] = _saved[key]
    return out


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")
