"""
utils/image.py
图片工具函数
AstrBot 的 image_result() 只接受路径字符串，不接受 bytes，
统一用此函数把 bytes 写到临时文件后返回路径。
"""

import os
import tempfile
from astrbot.api import logger


def save_image_bytes(img_bytes: bytes, suffix: str = ".png") -> str:
    """
    将图片 bytes 写入临时文件，返回文件路径。
    调用方在 yield image_result(path) 之后无需手动删除，
    系统 /tmp 会定期清理。
    """
    tmp = tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False, dir="/tmp"
    )
    try:
        tmp.write(img_bytes)
        tmp.flush()
        return tmp.name
    finally:
        tmp.close()
