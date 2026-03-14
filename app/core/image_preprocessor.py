"""图像预处理 — 二值化、去噪、倾斜校正（MVP 预留接口）。"""

from __future__ import annotations

from pathlib import Path


def preprocess(image_path: Path) -> Path:
    """MVP 阶段直接返回原图，后续可加入预处理逻辑。"""
    return image_path
