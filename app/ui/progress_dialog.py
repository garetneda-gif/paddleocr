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

_DIALOG_STYLE = """
    QDialog {
        background-color: #FFFFFF;
        border-radius: 16px;
    }
    QLabel#stageLabel {
        font-size: 15px;
        font-weight: 600;
        color: #1D1D1F;
    }
    QLabel#detailLabel {
        font-size: 12px;
        color: #6E6E73;
    }
    QProgressBar {
        border: none;
        border-radius: 5px;
        background-color: #E5E5EA;
        text-align: center;
        height: 10px;
    }
    QProgressBar::chunk {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #1A73E8, stop:1 #4A9CF5
        );
        border-radius: 5px;
    }
    QPushButton#cancelBtn {
        background-color: #F5F5F7;
        border: 1px solid #E5E5EA;
        border-radius: 8px;
        padding: 8px 24px;
        font-size: 13px;
        color: #6E6E73;
    }
    QPushButton#cancelBtn:hover {
        background-color: #E5E5EA;
        color: #1D1D1F;
    }
"""


class ProgressDialog(QDialog):
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("正在处理")
        self.setFixedSize(440, 180)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(12)

        self._stage_label = QLabel("正在初始化模型...")
        self._stage_label.setObjectName("stageLabel")
        layout.addWidget(self._stage_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._detail_label = QLabel("")
        self._detail_label.setObjectName("detailLabel")
        layout.addWidget(self._detail_label)

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setFixedWidth(100)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def update_progress(self, stage: str, page: int, total: int) -> None:
        self._stage_label.setText(stage)
        if total > 0:
            pct = int(page / total * 100)
            self._progress.setValue(pct)
            self._detail_label.setText(f"第 {page}/{total} 页  ({pct}%)")
        else:
            self._progress.setValue(0)
            self._detail_label.setText("")

    def _on_cancel(self) -> None:
        self._stage_label.setText("正在取消...")
        self.cancel_requested.emit()
