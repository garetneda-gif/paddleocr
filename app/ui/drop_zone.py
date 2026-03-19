"""拖拽区域组件 — 支持拖入多文件、文件夹、点击多选和剪贴板粘贴图片。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QFileDialog

from app.ui.theme import (
    ACCENT, BG_PRIMARY, BORDER_LIGHT, SUCCESS, SUCCESS_BG,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
)

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".pdf"}

_EXT_FILTER = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
_FILE_DIALOG_FILTER = f"支持的文件 ({_EXT_FILTER});;所有文件 (*)"


def _collect_files(path: Path) -> list[Path]:
    """收集路径下所有支持的文件（如果是文件夹则递归扫描）。"""
    if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
        return [path]
    if path.is_dir():
        found: list[Path] = []
        for child in sorted(path.rglob("*")):
            if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS:
                found.append(child)
        return found
    return []


_IDLE_STYLE = f"""
    #dropZone {{
        border: 2px dashed {BORDER_LIGHT};
        border-radius: 16px;
        background-color: #FAFAFA;
        min-height: 130px;
    }}
"""

_HOVER_STYLE = f"""
    #dropZone {{
        border: 2px solid {ACCENT};
        border-radius: 16px;
        background-color: #EEF4FD;
        min-height: 130px;
    }}
"""

_HAS_FILE_STYLE = f"""
    #dropZone {{
        border: 2px solid {SUCCESS};
        border-radius: 16px;
        background-color: {SUCCESS_BG};
        min-height: 130px;
    }}
"""


class DropZone(QWidget):
    file_dropped = Signal(Path)
    files_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(_IDLE_STYLE)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)

        self._icon = QLabel("\u2B06")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet(
            f"font-size: 32px; color: {BORDER_LIGHT}; background: transparent; border: none;"
        )
        layout.addWidget(self._icon)

        self._label = QLabel("拖拽图片、PDF 或文件夹到此处")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            f"font-size: 14px; color: {TEXT_SECONDARY}; font-weight: 500; "
            "background: transparent; border: none;"
        )
        layout.addWidget(self._label)

        self._sub = QLabel("点击选择  |  拖拽文件  |  \u2318V 粘贴截图")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub.setStyleSheet(
            f"font-size: 12px; color: {TEXT_TERTIARY}; background: transparent; border: none;"
        )
        layout.addWidget(self._sub)

        # 剪贴板粘贴快捷键（Cmd+V / Ctrl+V）
        self._paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        self._paste_shortcut.activated.connect(self._paste_from_clipboard)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择文件（可多选）",
            "",
            _FILE_DIALOG_FILTER,
        )
        if paths:
            file_list = [Path(p) for p in paths]
            if len(file_list) == 1:
                self.file_dropped.emit(file_list[0])
            self.files_dropped.emit(file_list)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(_HOVER_STYLE)
            self._icon.setStyleSheet(
                f"font-size: 32px; color: {ACCENT}; background: transparent; border: none;"
            )

    def dragLeaveEvent(self, event):
        self.setStyleSheet(_IDLE_STYLE)
        self._icon.setStyleSheet(
            f"font-size: 32px; color: {BORDER_LIGHT}; background: transparent; border: none;"
        )

    def dropEvent(self, event):
        self.setStyleSheet(_IDLE_STYLE)
        self._icon.setStyleSheet(
            f"font-size: 32px; color: {BORDER_LIGHT}; background: transparent; border: none;"
        )
        all_files: list[Path] = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            all_files.extend(_collect_files(path))

        if not all_files:
            return

        # 去重并保持顺序
        seen: set[Path] = set()
        unique: list[Path] = []
        for f in all_files:
            if f not in seen:
                seen.add(f)
                unique.append(f)

        if len(unique) == 1:
            self.file_dropped.emit(unique[0])
        self.files_dropped.emit(unique)

    def set_file_info(self, path: Path) -> None:
        self.setStyleSheet(_HAS_FILE_STYLE)
        self._icon.setText("\u2705")
        self._icon.setStyleSheet(
            f"font-size: 28px; color: {SUCCESS}; background: transparent; border: none;"
        )
        size = path.stat().st_size
        if size > 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{size / 1024:.1f} KB"
        self._label.setText(path.name)
        self._label.setStyleSheet(
            f"font-size: 14px; color: {TEXT_PRIMARY}; font-weight: 600; "
            "background: transparent; border: none;"
        )
        self._sub.setText(f"{size_str}  \u2022  点击重新选择")
        self._sub.setStyleSheet(
            f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )

    def _paste_from_clipboard(self) -> None:
        """从剪贴板粘贴图片，保存为临时文件后触发信号。"""
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()

        # 优先检查文件 URL（复制的文件）
        if mime.hasUrls():
            all_files: list[Path] = []
            for url in mime.urls():
                path = Path(url.toLocalFile())
                all_files.extend(_collect_files(path))
            if all_files:
                seen: set[Path] = set()
                unique: list[Path] = []
                for f in all_files:
                    if f not in seen:
                        seen.add(f)
                        unique.append(f)
                if len(unique) == 1:
                    self.file_dropped.emit(unique[0])
                self.files_dropped.emit(unique)
                return

        # 检查剪贴板图片（截图 / 复制的图片）
        image = clipboard.image()
        if image.isNull():
            return

        with tempfile.NamedTemporaryFile(
            suffix=".png", prefix="paddleocr_paste_", delete=False
        ) as f:
            tmp = Path(f.name)
        image.save(str(tmp), "PNG")
        if tmp.exists():
            self.file_dropped.emit(tmp)
            self.files_dropped.emit([tmp])

    def set_files_info(self, paths: list[Path]) -> None:
        if len(paths) == 1:
            self.set_file_info(paths[0])
            return
        self.setStyleSheet(_HAS_FILE_STYLE)
        self._icon.setText("\u2705")
        self._icon.setStyleSheet(
            f"font-size: 28px; color: {SUCCESS}; background: transparent; border: none;"
        )
        total_size = sum(p.stat().st_size for p in paths)
        size_mb = total_size / (1024 * 1024)
        self._label.setText(f"已选择 {len(paths)} 个文件（{size_mb:.1f} MB）")
        self._label.setStyleSheet(
            f"font-size: 14px; color: {TEXT_PRIMARY}; font-weight: 600; "
            "background: transparent; border: none;"
        )
        self._sub.setText(f"{paths[0].name} 等  \u2022  点击重新选择")
        self._sub.setStyleSheet(
            f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
