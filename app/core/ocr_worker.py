"""OCR 后台工作线程 — 逐页处理，流式输出，内存友好。"""

from __future__ import annotations

import gc
import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.models import BlockResult, DocumentResult, PageResult
from app.models.enums import OutputFormat
from app.models.job import OCRJob

_WORKER_STACK_SIZE = 64 * 1024 * 1024
_GC_INTERVAL = 10  # 每 N 页强制 GC


def _get_adv(job: OCRJob, key: str, default=None):
    return getattr(job, '_adv_params', {}).get(key, default)


def _auto_dpi(page_count: int, user_dpi: int) -> int:
    """大 PDF 自动降低 DPI，避免内存爆炸和长时间处理。"""
    if user_dpi > 0 and page_count <= 50:
        return user_dpi  # 用户设置的 DPI，小文档不降
    if page_count > 200:
        return min(user_dpi, 100)
    if page_count > 50:
        return min(user_dpi, 150)
    return user_dpi


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
        suffix = job.source_path.suffix.lower()
        is_pdf = suffix == ".pdf"
        fmt = job.output_format

        # 是否只需要纯文本（不需要 bbox/blocks）
        text_only = fmt in (OutputFormat.TXT, OutputFormat.RTF) and not job.preserve_layout

        # ── 1. 确定页数和 DPI ──
        if is_pdf:
            from app.core.pdf_processor import get_page_count
            self.progress.emit("正在读取 PDF...", 0, 0)
            total = get_page_count(job.source_path)
        else:
            total = 1

        # 页码范围
        page_start = _get_adv(job, "page_start", 1) - 1  # 转 0-based
        page_end = _get_adv(job, "page_end", total)
        page_start = max(0, min(page_start, total - 1))
        page_end = max(page_start + 1, min(page_end, total))
        actual_count = page_end - page_start

        # 自动 DPI
        user_dpi = _get_adv(job, "render_dpi", 200)
        dpi = _auto_dpi(actual_count, user_dpi)
        if dpi != user_dpi:
            self.progress.emit(
                f"共 {actual_count} 页，DPI 自动调整为 {dpi}（原 {user_dpi}）...", 0, actual_count
            )
        else:
            self.progress.emit(f"共 {actual_count} 页，正在初始化模型...", 0, actual_count)

        # ── 2. 初始化引擎 ──
        speed_mode = _get_adv(job, "speed_mode", "server")
        use_structure = self._should_use_structure(job)

        if use_structure:
            from app.core.structure_engine import StructureEngine
            engine = StructureEngine(lang=job.language)
        else:
            from app.core.ocr_engine import OCREngine
            engine = OCREngine(lang=job.language, speed_mode=speed_mode)

        engine._ensure_model()
        if self._cancel:
            return

        self.progress.emit("模型就绪，开始识别...", 0, actual_count)

        # ── 3. 逐页处理 ──
        all_pages: list[PageResult] = []
        all_texts: list[str] = []

        for seq, page_idx in enumerate(range(page_start, page_end)):
            if self._cancel:
                self.error.emit("用户取消了操作")
                return

            self.progress.emit(
                f"正在识别第 {seq + 1}/{actual_count} 页（DPI {dpi}）...",
                seq + 1, actual_count
            )

            # 渲染单页
            if is_pdf:
                from app.core.pdf_processor import render_page
                img_path = render_page(job.source_path, page_idx, dpi)
            else:
                img_path = job.source_path

            page_result = engine.predict(img_path)

            # 删除临时文件
            if is_pdf and img_path.exists():
                os.unlink(img_path)

            # 收集结果（text_only 模式只保留文本，不保留 blocks）
            if text_only:
                if page_result.plain_text:
                    all_texts.append(page_result.plain_text)
                # 不保留 blocks，节省大量内存
            else:
                for page in page_result.pages:
                    page.page_index = len(all_pages)
                    all_pages.append(page)
                if page_result.plain_text:
                    all_texts.append(page_result.plain_text)

            # 释放推理中间结果引用
            del page_result

            # 定期 GC
            if (seq + 1) % _GC_INTERVAL == 0:
                gc.collect()

        # 最终 GC
        gc.collect()

        result = DocumentResult(
            source_path=job.source_path,
            page_count=len(all_pages) if all_pages else actual_count,
            pages=all_pages,
            plain_text="\n".join(all_texts),
        )

        self.progress.emit("处理完成", actual_count, actual_count)
        self.finished.emit(result)

    def _should_use_structure(self, job: OCRJob) -> bool:
        # 允许高级参数覆盖
        pipeline = _get_adv(job, "pipeline", "auto")
        if pipeline == "ocr":
            return False
        if pipeline == "structure":
            return True
        # auto 模式
        fmt = job.output_format
        if fmt in (OutputFormat.WORD, OutputFormat.HTML, OutputFormat.EXCEL):
            return True
        if job.preserve_layout and fmt in (OutputFormat.TXT, OutputFormat.RTF):
            return True
        return False
