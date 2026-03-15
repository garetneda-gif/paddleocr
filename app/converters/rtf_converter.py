"""RTF 导出器 — 基础纯文本 + 段落格式。"""

from __future__ import annotations

from pathlib import Path

from app.converters.base_converter import BaseConverter
from app.models import DocumentResult, BlockType


class RtfConverter(BaseConverter):
    @property
    def file_extension(self) -> str:
        return ".rtf"

    def convert(self, result: DocumentResult, output_path: Path) -> Path:
        lines = [
            r"{\rtf1\ansi\deff0",
            r"{\fonttbl{\f0 Helvetica;}}",
            r"\f0\fs24",
            "",
        ]
        has_content = False

        for page in result.pages:
            for block in page.blocks:
                text = block.text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
                if not text:
                    continue
                if block.block_type == BlockType.TITLE:
                    lines.append(rf"\pard\b\fs32 {text}\b0\fs24\par")
                else:
                    lines.append(rf"\pard {text}\par")
                has_content = True
            if page.blocks:
                lines.append(r"\page")

        if not has_content and result.plain_text:
            for line in result.plain_text.splitlines():
                text = line.strip()
                if not text:
                    continue
                text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
                lines.append(rf"\pard {text}\par")
                has_content = True

        # 移除最后一个多余的 \page
        if lines and lines[-1] == r"\page":
            lines.pop()

        lines.append("}")

        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path
