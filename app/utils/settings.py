"""应用设置管理。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings


def get_settings() -> QSettings:
    return QSettings("PaddleOCR", "Desktop")


def last_output_dir() -> Path:
    s = get_settings()
    d = s.value("last_output_dir", "")
    if d and Path(d).is_dir():
        return Path(d)
    from app.utils.paths import default_output_dir
    return default_output_dir()


def set_last_output_dir(path: Path) -> None:
    s = get_settings()
    s.setValue("last_output_dir", str(path))
