"""OCR 进度对话框 — 显示处理阶段、页进度、耗时、速度、取消按钮。"""

from __future__ import annotations

import time

from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
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
    QLabel#timerLabel {
        font-size: 12px;
        color: #AEAEB2;
        font-variant-numeric: tabular-nums;
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


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


class ProgressDialog(QDialog):
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("正在处理")
        self.setFixedSize(480, 200)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(_DIALOG_STYLE)

        self._start_time = time.monotonic()
        self._last_page = 0
        self._total_pages = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(10)

        self._stage_label = QLabel("正在初始化模型...")
        self._stage_label.setObjectName("stageLabel")
        layout.addWidget(self._stage_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        # 详情行：左侧页码，右侧计时
        detail_row = QHBoxLayout()
        self._detail_label = QLabel("")
        self._detail_label.setObjectName("detailLabel")
        detail_row.addWidget(self._detail_label)
        detail_row.addStretch()
        self._timer_label = QLabel("0.0s")
        self._timer_label.setObjectName("timerLabel")
        detail_row.addWidget(self._timer_label)
        layout.addLayout(detail_row)

        # 速度/预估行
        self._speed_label = QLabel("")
        self._speed_label.setObjectName("detailLabel")
        layout.addWidget(self._speed_label)

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setFixedWidth(100)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # 每秒刷新计时器
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(500)

    def _tick(self) -> None:
        elapsed = time.monotonic() - self._start_time
        self._timer_label.setText(_fmt_duration(elapsed))

    def update_progress(self, stage: str, page: int, total: int) -> None:
        self._stage_label.setText(stage)
        self._last_page = page
        self._total_pages = total

        if total > 0:
            pct = int(page / total * 100)
            self._progress.setValue(pct)
            self._detail_label.setText(f"第 {page}/{total} 页  ({pct}%)")

            elapsed = time.monotonic() - self._start_time
            if page > 0 and elapsed > 0.5:
                speed = page / elapsed
                remaining = (total - page) / speed if speed > 0 else 0
                self._speed_label.setText(
                    f"{speed:.1f} 页/秒  \u2022  预计剩余 {_fmt_duration(remaining)}"
                )
            else:
                self._speed_label.setText("")
        else:
            self._progress.setValue(0)
            self._detail_label.setText("")
            self._speed_label.setText("")

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def _on_cancel(self) -> None:
        self._stage_label.setText("正在取消...")
        self.cancel_requested.emit()
