"""主窗口 — 整合侧边栏、快速转换面板、预览面板和进度对话框。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QLabel,
    QFileDialog,
)

from app.core.export_router import create_default_router
from app.core.ocr_worker import OCRWorker
from app.models import DocumentResult
from app.models.enums import OutputFormat
from app.models.job import OCRJob
from app.ui.preview_panel import PreviewPanel
from app.ui.progress_dialog import ProgressDialog
from app.ui.quick_convert_panel import QuickConvertPanel
from app.ui.sidebar import Sidebar
from app.utils.paths import default_output_dir


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PaddleOCR — 智能文档识别")
        self.setMinimumSize(960, 600)
        self.resize(1100, 700)

        self._worker: OCRWorker | None = None
        self._progress_dialog: ProgressDialog | None = None
        self._router = create_default_router()
        self._current_job: OCRJob | None = None

        self._setup_ui()
        self._load_styles()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 侧边栏
        self._sidebar = Sidebar()
        self._sidebar.page_changed.connect(self._on_page_changed)
        main_layout.addWidget(self._sidebar)

        # 中间主面板（堆叠多页面）
        self._stack = QStackedWidget()
        main_layout.addWidget(self._stack, 1)

        # 页面 0：快速转换
        self._quick_panel = QuickConvertPanel()
        self._quick_panel.start_requested.connect(self._on_start_convert)
        self._stack.addWidget(self._quick_panel)

        # 页面 1：高级选项（预留）
        advanced = QWidget()
        adv_layout = QVBoxLayout(advanced)
        adv_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        adv_label = QLabel("高级选项（开发中）")
        adv_label.setStyleSheet("font-size: 16px; color: #888;")
        adv_layout.addWidget(adv_label)
        self._stack.addWidget(advanced)

        # 页面 2：设置（预留）
        settings = QWidget()
        set_layout = QVBoxLayout(settings)
        set_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_label = QLabel("设置（开发中）")
        set_label.setStyleSheet("font-size: 16px; color: #888;")
        set_layout.addWidget(set_label)
        self._stack.addWidget(settings)

        # 右侧预览
        self._preview = PreviewPanel()
        main_layout.addWidget(self._preview)

    def _load_styles(self) -> None:
        from app.utils.paths import resources_dir
        qss_path = resources_dir() / "styles.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def _on_page_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    def _on_start_convert(self, file_path: Path, fmt: OutputFormat, lang: str) -> None:
        job = OCRJob(
            source_path=file_path,
            output_format=fmt,
            language=lang,
        )
        self._current_job = job

        # 显示预览
        if file_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"):
            self._preview.set_image(file_path)

        # 启动 worker
        self._worker = OCRWorker(job)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._progress_dialog = ProgressDialog(self)
        self._progress_dialog.cancel_requested.connect(self._on_cancel)
        self._progress_dialog.show()

        self._worker.start()

    def _on_progress(self, stage: str, current: int, total: int) -> None:
        if self._progress_dialog:
            self._progress_dialog.update_progress(stage, current, total)

    def _on_finished(self, result: DocumentResult) -> None:
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None

        self._preview.set_status(f"识别完成: {result.page_count} 页")

        # 导出
        try:
            job = self._current_job
            converter = self._router.select_converter(job.output_format)

            output_dir = default_output_dir()
            ext = converter.file_extension
            output_path = output_dir / (job.source_path.stem + ext)

            # 避免覆盖
            counter = 1
            while output_path.exists():
                output_path = output_dir / f"{job.source_path.stem}_{counter}{ext}"
                counter += 1

            converter.convert(result, output_path)

            reply = QMessageBox.information(
                self,
                "转换完成",
                f"文件已保存到:\n{output_path}\n\n是否打开文件？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._open_file(output_path)

        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _on_error(self, msg: str) -> None:
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        QMessageBox.warning(self, "处理出错", msg)

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()

    def _open_file(self, path: Path) -> None:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["start", str(path)], shell=True)
        else:
            subprocess.run(["xdg-open", str(path)])
