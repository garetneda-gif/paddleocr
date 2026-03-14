"""格式选择卡片组件。"""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.models.enums import OutputFormat

_FORMAT_INFO: dict[OutputFormat, tuple[str, str]] = {
    OutputFormat.TXT: ("TXT", "纯文本"),
    OutputFormat.PDF: ("PDF", "可搜索 PDF"),
    OutputFormat.WORD: ("Word", "保留版面结构"),
    OutputFormat.HTML: ("HTML", "网页格式"),
    OutputFormat.EXCEL: ("Excel", "表格数据"),
    OutputFormat.RTF: ("RTF", "富文本格式"),
}


class FormatCard(QWidget):
    selected = Signal(OutputFormat)

    def __init__(self, fmt: OutputFormat, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fmt = fmt
        self._is_selected = False
        self.setProperty("class", "FormatCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(120, 80)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title, desc = _FORMAT_INFO.get(fmt, (fmt.value.upper(), ""))
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(desc_label)

    def mousePressEvent(self, event):
        self.selected.emit(self._fmt)

    def set_selected(self, is_selected: bool) -> None:
        self._is_selected = is_selected
        self.setProperty("selected", "true" if is_selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)
