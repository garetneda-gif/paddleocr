"""OCR 后台工作线程 — 子进程批量隔离，内存可控。"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.models import BlockResult, BlockType, DocumentResult, PageResult
from app.models.enums import OutputFormat
from app.models.job import OCRJob
from app.core.ocr_subprocess import BATCH_SIZE

_WORKER_STACK_SIZE = 64 * 1024 * 1024


def _get_adv(job: OCRJob, key: str, default=None):
    return getattr(job, '_adv_params', {}).get(key, default)


def _auto_dpi(page_count: int, user_dpi: int) -> int:
    if page_count <= 50:
        return user_dpi
    if page_count > 200:
        return min(user_dpi, 100)
    return min(user_dpi, 150)


class OCRWorker(QThread):
    progress = Signal(str, int, int)
    finished = Signal(DocumentResult)
    error = Signal(str)

    def __init__(self, job: OCRJob, parent=None) -> None:
        super().__init__(parent)
        self.setStackSize(_WORKER_STACK_SIZE)
        self._job = job
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            self._do_work()
        except Exception as e:
            self.error.emit(str(e))

    def _do_work(self) -> None:
        job = self._job
        is_pdf = job.source_path.suffix.lower() == ".pdf"
        text_only = (
            job.output_format in (OutputFormat.TXT, OutputFormat.RTF)
            and not job.preserve_layout
        )

        # ── 1. 页数 + 文字层检测 ──
        if is_pdf:
            from app.core.pdf_processor import get_page_count, has_text_layer, extract_text_direct
            self.progress.emit("正在读取 PDF...", 0, 0)
            total = get_page_count(job.source_path)
        else:
            total = 1

        page_start = max(0, _get_adv(job, "page_start", 1) - 1)
        page_end = min(total, _get_adv(job, "page_end", total))
        actual = page_end - page_start

        # 智能检测：有文字层的 PDF 直接提取（除非用户勾选了"强制 OCR"）
        force_ocr = _get_adv(job, "force_ocr", False)
        if is_pdf and text_only and not force_ocr and has_text_layer(job.source_path):
            self.progress.emit("检测到 PDF 文字层，直接提取（无需 OCR）...", 0, actual)
            texts = extract_text_direct(job.source_path, page_start, page_end)
            doc = DocumentResult(
                source_path=job.source_path,
                page_count=actual,
                pages=[],
                plain_text="\n\n".join(t for t in texts if t.strip()),
            )
            self.progress.emit("提取完成", actual, actual)
            self.finished.emit(doc)
            return

        user_dpi = _get_adv(job, "render_dpi", 200)
        dpi = _auto_dpi(actual, user_dpi)
        speed_mode = _get_adv(job, "speed_mode", "server")

        mode_label = "Mobile" if speed_mode == "mobile" else "Server"
        self.progress.emit(f"{actual} 页 | DPI {dpi} | {mode_label} | OCR 模式", 0, actual)

        # ── 2. 分批子进程 OCR ──
        from app.core.ocr_subprocess import run_ocr_batch

        all_pages: list[PageResult] = []
        all_texts: list[str] = []
        pages_done = 0

        for batch_start in range(page_start, page_end, BATCH_SIZE):
            if self._cancel:
                self.error.emit("用户取消了操作")
                return

            batch_end = min(batch_start + BATCH_SIZE, page_end)
            batch_size = batch_end - batch_start

            self.progress.emit(
                f"正在识别第 {pages_done + 1}~{pages_done + batch_size}/{actual} 页...",
                pages_done, actual,
            )

            # 渲染本批次的页面
            batch_images: list[Path] = []
            if is_pdf:
                from app.core.pdf_processor import render_page
                for pi in range(batch_start, batch_end):
                    batch_images.append(render_page(job.source_path, pi, dpi))
            else:
                batch_images = [job.source_path]

            # 子进程批量 OCR（完成后自动释放内存）
            batch_results = run_ocr_batch(batch_images, job.language, speed_mode)

            # 删除临时图片
            if is_pdf:
                for img in batch_images:
                    if img.exists():
                        os.unlink(img)

            # 检查错误
            if batch_results and "error" in batch_results[0]:
                self.error.emit(batch_results[0]["error"])
                return

            # 收集结果
            for idx, page_data in enumerate(batch_results):
                page_texts = page_data.get("texts", [])
                if page_texts:
                    all_texts.append("\n".join(page_texts))

                if not text_only:
                    blocks = []
                    for b in page_data.get("blocks", []):
                        blocks.append(BlockResult(
                            block_type=BlockType.PARAGRAPH,
                            bbox=tuple(b["bbox"]),
                            text=b["text"],
                            confidence=b.get("score"),
                        ))
                    raw_blocks = page_data.get("blocks", [])
                    all_pages.append(PageResult(
                        page_index=pages_done + idx,
                        width=int(max((b["bbox"][2] for b in raw_blocks), default=0)),
                        height=int(max((b["bbox"][3] for b in raw_blocks), default=0)),
                        blocks=blocks,
                    ))

            pages_done += batch_size
            self.progress.emit(
                f"已完成 {pages_done}/{actual} 页",
                pages_done, actual,
            )

        doc = DocumentResult(
            source_path=job.source_path,
            page_count=actual,
            pages=all_pages,
            plain_text="\n\n".join(all_texts),
        )

        self.progress.emit("处理完成", actual, actual)
        self.finished.emit(doc)
