"""OCR 进度对话框 — 显示处理阶段、页进度、取消按钮。"""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class ProgressDialog(QDialog):
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("正在处理")
        self.setFixedSize(400, 160)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._stage_label = QLabel("正在初始化模型...")
        self._stage_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(self._stage_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._detail_label = QLabel("")
        self._detail_label.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(self._detail_label)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def update_progress(self, stage: str, page: int, total: int) -> None:
        self._stage_label.setText(stage)
        if total > 0:
            pct = int(page / total * 100)
            self._progress.setValue(pct)
            self._detail_label.setText(f"第 {page}/{total} 页")
        else:
            self._progress.setValue(0)
            self._detail_label.setText("")

    def _on_cancel(self) -> None:
        self._stage_label.setText("正在取消...")
        self.cancel_requested.emit()
