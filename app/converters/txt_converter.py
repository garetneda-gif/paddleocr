"""TXT 导出器 — 消费 plain_text。"""

from __future__ import annotations

from pathlib import Path

from app.converters.base_converter import BaseConverter
from app.models import DocumentResult


class TxtConverter(BaseConverter):
    @property
    def file_extension(self) -> str:
        return ".txt"

    def convert(self, result: DocumentResult, output_path: Path) -> Path:
        output_path.write_text(result.plain_text, encoding="utf-8")
        return output_path
