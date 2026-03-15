"""HTML 导出器 — 使用 bbox 坐标还原版面布局。"""

from __future__ import annotations

from pathlib import Path

from app.converters.base_converter import BaseConverter
from app.converters.layout_analyzer import analyze_page, Paragraph
from app.models import DocumentResult, BlockType


class HtmlConverter(BaseConverter):
    @property
    def file_extension(self) -> str:
        return ".html"

    def convert(self, result: DocumentResult, output_path: Path) -> Path:
        body_parts: list[str] = []

        for page_idx, page in enumerate(result.pages):
            if page_idx > 0:
                body_parts.append('<hr class="page-break">')

            if _has_semantic_blocks(page):
                body_parts.extend(_render_semantic_blocks(page.blocks))
                continue

            paragraphs = analyze_page(page)

            if not paragraphs:
                for block in page.blocks:
                    if block.text:
                        body_parts.append(f"<p>{_escape(block.text)}</p>")
                continue

            has_columns = any(p.column > 0 for p in paragraphs)
            in_columns = False

            for para in paragraphs:
                if has_columns and para.column > 0 and not in_columns:
                    body_parts.append('<div class="columns">')
                    in_columns = True
                elif has_columns and para.column == 0 and in_columns:
                    body_parts.append("</div>")
                    in_columns = False

                if para.block_type == BlockType.TITLE:
                    body_parts.append(f"<h1>{_escape(para.text)}</h1>")
                elif has_columns and para.column > 0:
                    col_class = "col-left" if para.column == 1 else "col-right"
                    body_parts.append(
                        f'<div class="{col_class}"><p>{_escape(para.text)}</p></div>'
                    )
                else:
                    text_html = _escape(para.text).replace("\n", "<br>")
                    body_parts.append(f"<p>{text_html}</p>")

            if in_columns:
                body_parts.append("</div>")

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
            "<style>\n"
            "body { font-family: 'SimSun', 'Songti SC', serif; max-width: 900px; "
            "margin: 2em auto; line-height: 1.8; color: #333; }\n"
            "h1 { text-align: center; font-size: 1.5em; margin: 1.2em 0 0.6em; }\n"
            "p { text-indent: 2em; margin: 0.4em 0; }\n"
            ".columns { display: flex; gap: 2em; }\n"
            ".col-left, .col-right { flex: 1; }\n"
            ".col-left p, .col-right p { text-indent: 2em; }\n"
            "hr.page-break { border: none; border-top: 1px dashed #ccc; margin: 2em 0; }\n"
            "table { border-collapse: collapse; width: 100%; margin: 1em 0; }\n"
            "td, th { border: 1px solid #ccc; padding: 8px; }\n"
            "</style>\n"
            "</head>\n<body>\n"
            + "\n".join(body_parts)
            + "\n</body>\n</html>"
        )

        output_path.write_text(html, encoding="utf-8")
        return output_path


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _has_semantic_blocks(page) -> bool:
    return any(
        block.block_type != BlockType.PARAGRAPH or block.table_cells
        for block in page.blocks
    )


def _render_semantic_blocks(blocks) -> list[str]:
    parts: list[str] = []
    for block in sorted(blocks, key=lambda item: (item.bbox[1], item.bbox[0])):
        if block.table_cells:
            rows: list[str] = []
            for row_idx, row in enumerate(block.table_cells):
                cell_tag = "th" if row_idx == 0 else "td"
                cells = "".join(
                    f"<{cell_tag}>{_escape(str(cell))}</{cell_tag}>"
                    for cell in row
                )
                rows.append(f"<tr>{cells}</tr>")
            parts.append("<table>\n" + "\n".join(rows) + "\n</table>")
            continue

        text = _escape(block.text).replace("\n", "<br>")
        if not text:
            continue
        if block.block_type == BlockType.TITLE:
            parts.append(f"<h1>{text}</h1>")
        else:
            parts.append(f"<p>{text}</p>")
    return parts
