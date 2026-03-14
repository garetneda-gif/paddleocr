"""导出器基类。"""

from __future__ import annotations

from pathlib import Path

from app.models import DocumentResult


class BaseConverter:
    """所有导出器的基类，子类需实现 convert 方法。"""

    def convert(self, result: DocumentResult, output_path: Path) -> Path:
        raise NotImplementedError

    @property
    def file_extension(self) -> str:
        raise NotImplementedError
