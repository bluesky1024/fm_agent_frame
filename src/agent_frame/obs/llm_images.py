"""历史模块名：图片落盘实现已移至 ``agent_frame.core.images``。

llm 与 obs 同层不能互相 import，因此实现放在 core，这里保留原导入路径。
"""

from agent_frame.core.images import save_images_and_strip

__all__ = ["save_images_and_strip"]
