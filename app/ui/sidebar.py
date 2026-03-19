"""左侧导航侧边栏。"""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget, QLabel

from app.ui.theme import ACCENT, BORDER_LIGHT, TEXT_TERTIARY, __version__


_NAV_ITEMS = [
    ("\u2B50", "转换"),
    ("\U0001F4C4", "预览"),
    ("\u2699\uFE0F", "设置"),
]


class Sidebar(QWidget):
    page_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(170)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 20)
        layout.setSpacing(4)

        app_label = QLabel("PaddleOCR")
        app_label.setStyleSheet(
            f"font-size: 17px; font-weight: 700; color: {ACCENT}; "
            "padding: 8px 8px; letter-spacing: 0.5px;"
        )
        layout.addWidget(app_label)

        ver_label = QLabel(f"v{__version__}  ONNX + Paddle")
        ver_label.setStyleSheet(
            f"font-size: 10px; color: {TEXT_TERTIARY}; padding: 0 8px 0 8px;"
        )
        layout.addWidget(ver_label)
        layout.addSpacing(20)

        self._buttons: list[QPushButton] = []
        for i, (icon, title) in enumerate(_NAV_ITEMS):
            btn = QPushButton(f"  {icon}  {title}")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self._on_click(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

        footer = QLabel("Powered by PP-OCRv5")
        footer.setStyleSheet(
            f"font-size: 10px; color: {BORDER_LIGHT}; padding: 4px 8px;"
        )
        layout.addWidget(footer)

        self._buttons[0].setChecked(True)

    def _on_click(self, index: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
        self.page_changed.emit(index)
