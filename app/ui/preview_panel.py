"""OCR 结果预览面板 — 左侧原图 + 右侧识别文本，支持翻页和复制全文。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal as _Signal
from PySide6.QtGui import QPixmap, QImage, QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models import DocumentResult
from app.ui.theme import (
    ACCENT, ACCENT_BG, ACCENT_HOVER,
    BG_PRIMARY, BG_SECONDARY, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    RADIUS,
)


# ── 样式常量（引用 theme 令牌） ──

_CARD_STYLE = (
    f"background-color: {BG_PRIMARY}; border: 1px solid {BORDER}; "
    f"border-radius: {RADIUS};"
)

_HEADER_BADGE_STYLE = (
    "font-size: 11px; font-weight: 600; color: {fg}; "
    "background-color: {bg}; border-radius: 4px; padding: 2px 8px;"
)

_NAV_BTN_STYLE = f"""
    QPushButton {{
        background-color: {BG_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 6px 16px;
        font-size: 13px;
        color: {TEXT_PRIMARY};
    }}
    QPushButton:hover {{
        background-color: {ACCENT_BG};
        border-color: {ACCENT};
        color: {ACCENT};
    }}
    QPushButton:disabled {{
        color: {TEXT_TERTIARY};
        border-color: {BORDER};
        background-color: {BG_SECONDARY};
    }}
"""

_TEXT_EDIT_STYLE = f"""
    QTextEdit {{
        font-size: 13px;
        line-height: 1.7;
        color: {TEXT_PRIMARY};
        background-color: {BG_SECONDARY};
        border: none;
        border-radius: 8px;
        padding: 12px;
        selection-background-color: {ACCENT_BG};
    }}
"""

_SCROLL_AREA_STYLE = f"""
    QScrollArea {{
        background-color: {BG_SECONDARY};
        border: none;
        border-radius: 8px;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: {BG_SECONDARY};
    }}
"""

_COPY_BTN_STYLE = f"""
    QPushButton {{
        background-color: {BG_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 3px 10px;
        font-size: 11px;
        color: {TEXT_SECONDARY};
    }}
    QPushButton:hover {{
        background-color: {ACCENT_BG};
        border-color: {ACCENT};
        color: {ACCENT};
    }}
"""


# ── 异步图片加载线程 ──

class _PageImageLoader(QThread):
    """后台加载页面图片，避免大 PDF 冻结 UI。"""

    finished = _Signal(list)  # list[QPixmap]

    def __init__(self, source: Path, pages: list, parent=None):
        super().__init__(parent)
        self._source = source
        self._pages = pages

    def run(self):
        images: list[QPixmap] = []
        is_pdf = self._source.suffix.lower() == ".pdf"

        if is_pdf:
            try:
                import fitz
                doc = fitz.open(str(self._source))
                for page in self._pages:
                    pi = page.page_index
                    if pi < len(doc):
                        pix = doc[pi].get_pixmap(dpi=150)
                        img = QImage(
                            pix.samples, pix.width, pix.height,
                            pix.stride, QImage.Format.Format_RGB888,
                        )
                        images.append(QPixmap.fromImage(img))
                    else:
                        images.append(QPixmap())
                doc.close()
            except Exception:
                for _ in self._pages:
                    images.append(QPixmap())
        else:
            pix = QPixmap(str(self._source))
            for _ in self._pages:
                images.append(pix)

        self.finished.emit(images)


class PreviewPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG_SECONDARY};")

        self._result: DocumentResult | None = None
        self._page_images: list[QPixmap] = []
        self._scaled_cache: dict[int, tuple[int, QPixmap]] = {}
        self._current_page: int = 0
        self._loader: _PageImageLoader | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ── 空状态占位 ──
        self._empty_widget = QWidget()
        self._empty_widget.setStyleSheet(f"background-color: {BG_SECONDARY};")
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.addStretch(2)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            f"font-size: 56px; color: {TEXT_TERTIARY}; background: transparent;"
        )
        icon_label.setText("\U0001F50D")
        empty_layout.addWidget(icon_label)
        empty_layout.addSpacing(12)

        empty_title = QLabel("OCR 结果预览")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {TEXT_PRIMARY}; background: transparent;"
        )
        empty_layout.addWidget(empty_title)
        empty_layout.addSpacing(6)

        empty_sub = QLabel("完成转换后自动显示识别结果")
        empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_sub.setStyleSheet(
            f"font-size: 14px; color: {TEXT_SECONDARY}; background: transparent;"
        )
        empty_layout.addWidget(empty_sub)
        empty_layout.addSpacing(20)

        steps = [
            "\u2460  在「转换」页选择文件并开始识别",
            "\u2461  等待 OCR 处理完成",
            "\u2462  结果将在此处自动展示",
        ]
        for step_text in steps:
            step = QLabel(step_text)
            step.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step.setStyleSheet(
                f"font-size: 13px; color: {TEXT_TERTIARY}; background: transparent; "
                "padding: 2px 0;"
            )
            empty_layout.addWidget(step)

        empty_layout.addStretch(3)
        layout.addWidget(self._empty_widget, 1)

        # ── 内容区域 ──
        self._content = QWidget()
        self._content.setStyleSheet(f"background-color: {BG_SECONDARY};")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # 顶部：标题 + 页码导航
        top_bar = QHBoxLayout()
        title = QLabel("OCR 结果预览")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {TEXT_PRIMARY}; background: transparent;"
        )
        top_bar.addWidget(title)

        self._page_badge = QLabel()
        self._page_badge.setStyleSheet(
            _HEADER_BADGE_STYLE.format(fg=ACCENT, bg=ACCENT_BG)
        )
        self._page_badge.setVisible(False)
        top_bar.addWidget(self._page_badge)

        top_bar.addStretch()

        self._prev_btn = QPushButton("\u276E  上一页")
        self._prev_btn.setStyleSheet(_NAV_BTN_STYLE)
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_btn.clicked.connect(self._prev_page)
        top_bar.addWidget(self._prev_btn)

        self._page_label = QLabel("0 / 0")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setFixedWidth(64)
        self._page_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {TEXT_SECONDARY}; background: transparent;"
        )
        top_bar.addWidget(self._page_label)

        self._next_btn = QPushButton("下一页  \u276F")
        self._next_btn.setStyleSheet(_NAV_BTN_STYLE)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(self._next_page)
        top_bar.addWidget(self._next_btn)

        content_layout.addLayout(top_bar)

        # 分栏 — 增加视觉手柄提示
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background-color: {BORDER}; width: 2px; margin: 40px 3px; border-radius: 1px; }}"
        )
        splitter.setHandleWidth(8)

        # 左侧：原图预览（卡片）
        left_card = QWidget()
        left_card.setStyleSheet(_CARD_STYLE)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(12, 10, 12, 12)
        left_layout.setSpacing(8)

        left_header = QLabel("原始文档")
        left_header.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {TEXT_SECONDARY}; "
            "letter-spacing: 1px; text-transform: uppercase; border: none; background: transparent;"
        )
        left_layout.addWidget(left_header)

        self._image_scroll = QScrollArea()
        self._image_scroll.setWidgetResizable(True)
        self._image_scroll.setStyleSheet(_SCROLL_AREA_STYLE)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("background: transparent; padding: 4px;")
        self._image_scroll.setWidget(self._image_label)
        left_layout.addWidget(self._image_scroll, 1)

        splitter.addWidget(left_card)

        # 右侧：OCR 文本（卡片）
        right_card = QWidget()
        right_card.setStyleSheet(_CARD_STYLE)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(12, 10, 12, 12)
        right_layout.setSpacing(8)

        right_header_row = QHBoxLayout()
        right_header = QLabel("识别结果")
        right_header.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {TEXT_SECONDARY}; "
            "letter-spacing: 1px; text-transform: uppercase; border: none; background: transparent;"
        )
        right_header_row.addWidget(right_header)

        self._char_count_label = QLabel()
        self._char_count_label.setStyleSheet(
            f"font-size: 11px; color: {TEXT_TERTIARY}; border: none; background: transparent;"
        )
        right_header_row.addStretch()

        # 复制全文按钮
        self._copy_btn = QPushButton("复制全文")
        self._copy_btn.setStyleSheet(_COPY_BTN_STYLE)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(self._copy_all_text)
        right_header_row.addWidget(self._copy_btn)

        right_header_row.addWidget(self._char_count_label)
        right_layout.addLayout(right_header_row)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setStyleSheet(_TEXT_EDIT_STYLE)
        font = QFont()
        font.setFamilies(["PingFang SC", "SF Pro Text", "Helvetica Neue", "sans-serif"])
        font.setPointSize(13)
        self._text_edit.setFont(font)
        right_layout.addWidget(self._text_edit, 1)

        splitter.addWidget(right_card)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        content_layout.addWidget(splitter, 1)

        self._content.setVisible(False)
        layout.addWidget(self._content, 1)

    def _stop_loader(self) -> None:
        """安全停止旧的图片加载线程。"""
        if self._loader is not None:
            self._loader.finished.disconnect()
            self._loader.quit()
            self._loader.wait(2000)
            self._loader = None

    def set_result(self, result: DocumentResult) -> None:
        """接收 OCR 结果并显示预览。"""
        self._stop_loader()
        self._page_images.clear()
        self._scaled_cache.clear()

        self._result = result
        self._current_page = 0

        # 异步加载页面图片
        self._page_images = [QPixmap()] * len(result.pages)
        self._image_label.setText("正在加载预览图...")
        self._image_label.setStyleSheet(
            f"color: {TEXT_TERTIARY}; font-size: 14px; background: transparent;"
        )

        self._loader = _PageImageLoader(result.source_path, result.pages, self)
        self._loader.finished.connect(self._on_images_loaded)
        self._loader.start()

        self._empty_widget.setVisible(False)
        self._content.setVisible(True)

        total = len(result.pages) if result.pages else 0
        if total > 1:
            self._page_badge.setText(f"{total} 页")
            self._page_badge.setVisible(True)
        else:
            self._page_badge.setVisible(False)

        self._show_page(0)

    def _on_images_loaded(self, images: list[QPixmap]) -> None:
        """图片加载完成回调。"""
        self._page_images = images
        self._loader = None
        self._show_page(self._current_page)

    def _show_page(self, idx: int) -> None:
        """显示指定页。"""
        if self._result is None or not self._result.pages:
            return

        total = len(self._result.pages)
        idx = max(0, min(idx, total - 1))
        self._current_page = idx

        # 更新页码 — 始终显示页码标签区域
        self._page_label.setText(f"{idx + 1} / {total}")
        self._prev_btn.setEnabled(idx > 0)
        self._next_btn.setEnabled(idx < total - 1)

        # 单页时隐藏翻页按钮但保留页码标签
        single = total <= 1
        self._prev_btn.setVisible(not single)
        self._next_btn.setVisible(not single)

        # 左侧图片（带缩放缓存）
        if idx < len(self._page_images) and not self._page_images[idx].isNull():
            target_w = max(400, self._image_scroll.width() - 30)
            cached = self._scaled_cache.get(idx)
            if cached is not None and cached[0] == target_w:
                scaled = cached[1]
            else:
                scaled = self._page_images[idx].scaledToWidth(
                    target_w,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._scaled_cache[idx] = (target_w, scaled)
            self._image_label.setPixmap(scaled)
        else:
            self._image_label.setText("正在加载预览图...")
            self._image_label.setStyleSheet(
                f"color: {TEXT_TERTIARY}; font-size: 14px; background: transparent;"
            )

        # 右侧文本
        page_result = self._result.pages[idx]
        text_parts: list[str] = []
        for block in page_result.blocks:
            if block.text:
                text_parts.append(block.text)
        full_text = "\n\n".join(text_parts)
        self._text_edit.setPlainText(full_text)

        # 字符统计
        char_count = len(full_text.replace("\n", "").replace(" ", ""))
        self._char_count_label.setText(f"{char_count} 字")

    def _copy_all_text(self) -> None:
        """复制所有页的 OCR 文本到剪贴板。"""
        if self._result is None:
            return
        all_texts: list[str] = []
        for page in self._result.pages:
            for block in page.blocks:
                if block.text:
                    all_texts.append(block.text)
        QApplication.clipboard().setText("\n\n".join(all_texts))
        self._copy_btn.setText("已复制")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self._copy_btn.setText("复制全文"))

    def _prev_page(self) -> None:
        self._show_page(self._current_page - 1)

    def _next_page(self) -> None:
        self._show_page(self._current_page + 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._scaled_cache.clear()

    def clear(self) -> None:
        self._stop_loader()
        self._result = None
        self._page_images.clear()
        self._scaled_cache.clear()
        self._current_page = 0
        self._empty_widget.setVisible(True)
        self._content.setVisible(False)
        self._image_label.clear()
        self._text_edit.clear()
        self._char_count_label.clear()
        self._page_badge.setVisible(False)
