"""PDF 处理 — 逐页渲染，用完释放，避免内存爆炸。"""

from __future__ import annotations

import tempfile
from pathlib import Path

RENDER_DPI = 200  # 从 300 降到 200，大幅减少内存且质量够用


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

    tmp = Path(tempfile.mktemp(suffix=f"_p{page_index:04d}.png", prefix="pocr_"))
    pix.save(str(tmp))

    pix = None
    doc.close()
    return tmp


def extract_pages(pdf_path: Path, dpi: int = RENDER_DPI) -> list[Path]:
    """兼容旧接口：一次性提取所有页面（仅用于小 PDF）。"""
    count = get_page_count(pdf_path)
    return [render_page(pdf_path, i, dpi) for i in range(count)]
