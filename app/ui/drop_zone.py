"""拖拽区域组件 — 支持拖入文件和点击选择。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QFileDialog

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".pdf"}


class DropZone(QWidget):
    file_dropped = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel("拖拽图片或 PDF 到此处\n或点击选择文件")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(self._label)

    def mousePressEvent(self, event):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            "",
            "支持的文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.pdf);;所有文件 (*)",
        )
        if path:
            self.file_dropped.emit(Path(path))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("#dropZone { border-color: #1A73E8; background-color: #F0F4FF; }")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event):
        self.setStyleSheet("")
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                self.file_dropped.emit(path)
                return

    def set_file_info(self, path: Path) -> None:
        self._label.setText(f"已选择: {path.name}\n({path.stat().st_size / 1024:.1f} KB)")
