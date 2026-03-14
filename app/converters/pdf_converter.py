"""可搜索 PDF 导出器 — 在原始图像上叠加透明文字层。"""

from __future__ import annotations

from pathlib import Path

from app.converters.base_converter import BaseConverter
from app.models import DocumentResult
from app.core.pdf_processor import RENDER_DPI


class PdfConverter(BaseConverter):
    @property
    def file_extension(self) -> str:
        return ".pdf"

    def convert(self, result: DocumentResult, output_path: Path) -> Path:
        import fitz

        doc = fitz.open()

        source = result.source_path
        if source.suffix.lower() == ".pdf":
            src_doc = fitz.open(str(source))
        else:
            src_doc = None

        for page_result in result.pages:
            if src_doc and page_result.page_index < len(src_doc):
                # PDF 输入：复制原始页面
                pdf_page = doc.new_page(
                    width=src_doc[page_result.page_index].rect.width,
                    height=src_doc[page_result.page_index].rect.height,
                )
                pdf_page.show_pdf_page(pdf_page.rect, src_doc, page_result.page_index)
                scale = pdf_page.rect.width / page_result.width if page_result.width else 1
            else:
                # 图片输入：将图片作为背景
                img_path = result.source_path
                img_rect = fitz.Rect(0, 0, page_result.width, page_result.height)
                # 转换为 72 DPI 的 PDF 点
                scale = 72.0 / RENDER_DPI
                pdf_rect = fitz.Rect(
                    0, 0,
                    page_result.width * scale,
                    page_result.height * scale,
                )
                pdf_page = doc.new_page(width=pdf_rect.width, height=pdf_rect.height)
                pdf_page.insert_image(pdf_rect, filename=str(img_path))

            # 叠加透明文字层
            for block in page_result.blocks:
                if not block.text:
                    continue
                x1, y1, x2, y2 = block.bbox
                text_rect = fitz.Rect(
                    x1 * scale, y1 * scale,
                    x2 * scale, y2 * scale,
                )
                fontsize = max((y2 - y1) * scale * 0.7, 6)
                pdf_page.insert_textbox(
                    text_rect,
                    block.text,
                    fontsize=fontsize,
                    color=(0, 0, 0),
                    opacity=0,  # 透明文字层
                )

        if src_doc:
            src_doc.close()

        doc.save(str(output_path))
        doc.close()
        return output_path
