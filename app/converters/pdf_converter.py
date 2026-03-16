"""可搜索 PDF 导出器 — 在原始图像上叠加透明文字层。"""

from __future__ import annotations

from pathlib import Path

from app.converters.base_converter import BaseConverter
from app.models import DocumentResult
from app.core.pdf_processor import RENDER_DPI

# CJK Unicode 范围（中日韩统一表意文字 + 常用扩展）
_CJK_RANGES = (
    (0x3000, 0x303F),  # CJK 符号和标点
    (0x3040, 0x30FF),  # 平假名 + 片假名
    (0x4E00, 0x9FFF),  # CJK 统一表意文字
    (0x3400, 0x4DBF),  # CJK 扩展 A
    (0xAC00, 0xD7AF),  # 韩文音节
    (0xFF00, 0xFFEF),  # 全角字符
)


def _needs_cjk_font(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        for lo, hi in _CJK_RANGES:
            if lo <= cp <= hi:
                return True
    return False


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

        # 检测文档是否含 CJK 文字，选择对应字体
        has_cjk = any(
            _needs_cjk_font(block.text)
            for page in result.pages
            for block in page.blocks
            if block.text
        )
        fontname = "china-s" if has_cjk else "helv"

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
                # 转换为 72 DPI 的 PDF 点
                scale = 72.0 / RENDER_DPI
                pdf_rect = fitz.Rect(
                    0, 0,
                    page_result.width * scale,
                    page_result.height * scale,
                )
                pdf_page = doc.new_page(width=pdf_rect.width, height=pdf_rect.height)
                pdf_page.insert_image(pdf_rect, filename=str(img_path))

            # 叠加不可见但可选取的文字层（PDF render_mode=3）
            for block in page_result.blocks:
                if not block.text:
                    continue
                x1, y1, x2, y2 = block.bbox
                fontsize = max((y2 - y1) * scale * 0.5, 4)
                baseline = fitz.Point(x1 * scale, y1 * scale + fontsize)
                pdf_page.insert_text(
                    baseline,
                    block.text,
                    fontname=fontname,
                    fontsize=fontsize,
                    render_mode=3,  # 不可见但可搜索/选取/复制
                )

        if src_doc:
            src_doc.close()

        doc.save(str(output_path))
        doc.close()
        return output_path
