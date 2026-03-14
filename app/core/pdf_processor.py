"""PDF 处理 — 将 PDF 页面渲染为图片供 OCR 引擎处理。"""

from __future__ import annotations

import tempfile
from pathlib import Path

RENDER_DPI = 300


def extract_pages(pdf_path: Path, dpi: int = RENDER_DPI) -> list[Path]:
    """将 PDF 的每一页渲染为 PNG 图片，返回临时文件路径列表。"""
    import fitz

    doc = fitz.open(str(pdf_path))
    paths: list[Path] = []

    tmp_dir = Path(tempfile.mkdtemp(prefix="paddleocr_"))
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        out_path = tmp_dir / f"page_{i:04d}.png"
        pix.save(str(out_path))
        paths.append(out_path)

    doc.close()
    return paths


def get_page_count(pdf_path: Path) -> int:
    import fitz

    doc = fitz.open(str(pdf_path))
    count = len(doc)
    doc.close()
    return count
