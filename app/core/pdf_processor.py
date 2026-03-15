"""PDF 处理 — 智能检测文字层，有文字层直接提取，无则 OCR。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

RENDER_DPI = 200


def _safe_temp_path(*, suffix: str, prefix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    return Path(name)


def has_text_layer(pdf_path: Path, sample_pages: int = 5) -> bool:
    """检测 PDF 是否有可提取的文字层（非扫描件）。"""
    import fitz
    doc = fitz.open(str(pdf_path))
    pages_with_text = 0
    check_count = min(sample_pages, len(doc))
    if check_count == 0:
        doc.close()
        return False
    for i in range(check_count):
        text = doc[i].get_text().strip()
        if len(text) > 20:  # 至少 20 字符才算有文字层
            pages_with_text += 1
    doc.close()
    return pages_with_text >= check_count * 0.6  # 60% 以上页面有文字


def extract_text_direct(
    pdf_path: Path, page_start: int = 0, page_end: int | None = None
) -> list[str]:
    """直接从 PDF 文字层提取文本（毫秒级，不需要 OCR）。"""
    import fitz
    doc = fitz.open(str(pdf_path))
    if page_end is None:
        page_end = len(doc)

    texts = []
    for i in range(page_start, min(page_end, len(doc))):
        texts.append(doc[i].get_text())
    doc.close()
    return texts


def get_page_count(pdf_path: Path) -> int:
    import fitz
    doc = fitz.open(str(pdf_path))
    count = len(doc)
    doc.close()
    return count


def render_page(pdf_path: Path, page_index: int, dpi: int = RENDER_DPI) -> Path:
    """渲染单页 PDF 为 PNG，返回临时文件路径。"""
    import fitz

    doc = fitz.open(str(pdf_path))
    page = doc[page_index]

    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)

    tmp = _safe_temp_path(suffix=f"_p{page_index:04d}.png", prefix="pocr_")
    pix.save(str(tmp))

    pix = None
    doc.close()
    return tmp


def extract_pages(pdf_path: Path, dpi: int = RENDER_DPI) -> list[Path]:
    """兼容旧接口：一次性提取所有页面（仅用于小 PDF）。"""
    count = get_page_count(pdf_path)
    return [render_page(pdf_path, i, dpi) for i in range(count)]
