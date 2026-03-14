"""HTML 导出器 — 优先使用 markdown 中转，降级使用 blocks。"""

from __future__ import annotations

from pathlib import Path

from app.converters.base_converter import BaseConverter
from app.models import DocumentResult, BlockType


class HtmlConverter(BaseConverter):
    @property
    def file_extension(self) -> str:
        return ".html"

    def convert(self, result: DocumentResult, output_path: Path) -> Path:
        body_parts: list[str] = []

        for page in result.pages:
            for block in page.blocks:
                if block.html:
                    body_parts.append(block.html)
                elif block.block_type == BlockType.TITLE:
                    body_parts.append(f"<h1>{_escape(block.text)}</h1>")
                elif block.block_type == BlockType.TABLE and block.table_cells:
                    body_parts.append(self._cells_to_html(block.table_cells))
                elif block.text:
                    body_parts.append(f"<p>{_escape(block.text)}</p>")

        # 降级
        if not body_parts and result.plain_text:
            for line in result.plain_text.split("\n"):
                if line.strip():
                    body_parts.append(f"<p>{_escape(line)}</p>")

        html = (
            "<!DOCTYPE html>\n"
            '<html lang="zh">\n<head>\n'
            '<meta charset="utf-8">\n'
            "<title>OCR Result</title>\n"
            "<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:2em auto;"
            "line-height:1.6;} table{border-collapse:collapse;width:100%;margin:1em 0;} "
            "td,th{border:1px solid #ccc;padding:8px;}</style>\n"
            "</head>\n<body>\n"
            + "\n".join(body_parts)
            + "\n</body>\n</html>"
        )

        output_path.write_text(html, encoding="utf-8")
        return output_path

    def _cells_to_html(self, cells: list[list[str]]) -> str:
        rows = []
        for i, row in enumerate(cells):
            tag = "th" if i == 0 else "td"
            row_html = "".join(f"<{tag}>{_escape(str(c))}</{tag}>" for c in row)
            rows.append(f"<tr>{row_html}</tr>")
        return f"<table>{''.join(rows)}</table>"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
