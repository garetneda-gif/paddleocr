"""统一路径管理 — 所有用户目录访问必须经过此模块。"""

from __future__ import annotations

import sys
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_root() -> Path:
    if _is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent


def resources_dir() -> Path:
    return app_root() / "resources"


def default_output_dir() -> Path:
    d = Path.home() / "Documents" / "PaddleOCR Output"
    d.mkdir(parents=True, exist_ok=True)
    return d
