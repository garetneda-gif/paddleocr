"""Word (DOCX) 导出器 — 消费 blocks 中的结构化结果。"""

from __future__ import annotations

from pathlib import Path

from app.converters.base_converter import BaseConverter
from app.models import DocumentResult, BlockType


class WordConverter(BaseConverter):
    @property
    def file_extension(self) -> str:
        return ".docx"

    def convert(self, result: DocumentResult, output_path: Path) -> Path:
        from docx import Document
        from docx.shared import Pt

        doc = Document()

        for page in result.pages:
            for block in page.blocks:
                if block.block_type == BlockType.TITLE:
                    doc.add_heading(block.text, level=1)
                elif block.block_type == BlockType.TABLE and block.table_cells:
                    self._add_table(doc, block.table_cells)
                elif block.block_type == BlockType.TABLE and block.html:
                    # 降级：表格无 cell 数据时，以纯文本输出 HTML 标记
                    doc.add_paragraph(f"[表格] {block.text or block.html[:200]}")
                else:
                    if block.text:
                        doc.add_paragraph(block.text)

        # 降级：如果没有 blocks，使用 plain_text
        if not any(page.blocks for page in result.pages) and result.plain_text:
            for line in result.plain_text.split("\n"):
                if line.strip():
                    doc.add_paragraph(line)

        doc.save(str(output_path))
        return output_path

    def _add_table(self, doc, cells: list[list[str]]) -> None:
        if not cells:
            return
        rows = len(cells)
        cols = max(len(row) for row in cells) if cells else 0
        if cols == 0:
            return

        table = doc.add_table(rows=rows, cols=cols, style="Table Grid")
        for i, row in enumerate(cells):
            for j, cell_text in enumerate(row):
                if j < cols:
                    table.rows[i].cells[j].text = str(cell_text)
