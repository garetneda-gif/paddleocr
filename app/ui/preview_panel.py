"""右侧预览面板 — 显示页面缩略图和处理状态。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget


class PreviewPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("预览")
        header.setStyleSheet("font-size: 14px; font-weight: 600; color: #333;")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._container)

        self._thumb_label = QLabel("暂无预览")
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_label.setStyleSheet("color: #888; padding: 20px;")
        self._container_layout.addWidget(self._thumb_label)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(self._status_label)

    def set_image(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._thumb_label.setText("无法加载预览")
            return
        scaled = pixmap.scaledToWidth(200, Qt.TransformationMode.SmoothTransformation)
        self._thumb_label.setPixmap(scaled)
        self._thumb_label.setText("")

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def clear(self) -> None:
        self._thumb_label.setPixmap(QPixmap())
        self._thumb_label.setText("暂无预览")
        self._status_label.setText("")
