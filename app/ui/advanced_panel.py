"""高级选项面板 — 暴露 PaddleOCR 的全部可配置能力。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.utils.language_map import LANGUAGES


class AdvancedPanel(QWidget):
    """高级选项面板，暴露 PaddleOCR / PPStructureV3 的核心参数。"""

    start_requested = Signal(dict)  # 完整参数字典

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        title = QLabel("高级选项")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        main_layout.addWidget(title)

        # ── 输入文件 ──
        input_group = QGroupBox("输入文件")
        input_layout = QHBoxLayout(input_group)
        self._file_path = QLineEdit()
        self._file_path.setPlaceholderText("选择图片或 PDF 文件...")
        self._file_path.setReadOnly(True)
        input_layout.addWidget(self._file_path)
        browse_btn = QPushButton("浏览")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_file)
        input_layout.addWidget(browse_btn)
        main_layout.addWidget(input_group)

        # ── Pipeline 选择 ──
        pipeline_group = QGroupBox("识别模式")
        pipeline_layout = QVBoxLayout(pipeline_group)

        pl_row = QHBoxLayout()
        pl_row.addWidget(QLabel("Pipeline："))
        self._pipeline_combo = QComboBox()
        self._pipeline_combo.addItem("自动（按输出格式决定）", "auto")
        self._pipeline_combo.addItem("PP-OCRv5（纯文本识别）", "ocr")
        self._pipeline_combo.addItem("PPStructureV3（结构化解析）", "structure")
        self._pipeline_combo.setFixedWidth(280)
        pl_row.addWidget(self._pipeline_combo)
        pl_row.addStretch()
        pipeline_layout.addLayout(pl_row)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("识别语言："))
        self._lang_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self._lang_combo.addItem(f"{name} ({code})", code)
        self._lang_combo.setFixedWidth(280)
        lang_row.addWidget(self._lang_combo)
        lang_row.addStretch()
        pipeline_layout.addLayout(lang_row)

        main_layout.addWidget(pipeline_group)

        # ── 文档预处理 ──
        preproc_group = QGroupBox("文档预处理")
        preproc_layout = QVBoxLayout(preproc_group)

        self._orientation_check = QCheckBox("文档方向检测与校正（use_doc_orientation_classify）")
        self._orientation_check.setToolTip("自动检测文档是否旋转 90°/180°/270° 并校正")
        preproc_layout.addWidget(self._orientation_check)

        self._unwarp_check = QCheckBox("文档弯曲矫正（use_doc_unwarping）")
        self._unwarp_check.setToolTip("对拍照弯曲的文档进行几何校正")
        preproc_layout.addWidget(self._unwarp_check)

        self._textline_ori_check = QCheckBox("文本行方向检测（use_textline_orientation）")
        self._textline_ori_check.setToolTip("检测文本行是否为竖排并校正，仅 PP-OCRv5 可用")
        preproc_layout.addWidget(self._textline_ori_check)

        main_layout.addWidget(preproc_group)

        # ── PDF 设置 ──
        pdf_group = QGroupBox("PDF 输入设置")
        pdf_layout = QVBoxLayout(pdf_group)

        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("渲染 DPI："))
        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(72, 600)
        self._dpi_spin.setValue(300)
        self._dpi_spin.setFixedWidth(100)
        self._dpi_spin.setToolTip("PDF 渲染为图片的分辨率，越高越清晰但越慢")
        dpi_row.addWidget(self._dpi_spin)
        dpi_row.addWidget(QLabel("（推荐 200~300）"))
        dpi_row.addStretch()
        pdf_layout.addLayout(dpi_row)

        main_layout.addWidget(pdf_group)

        # ── 输出设置 ──
        output_group = QGroupBox("输出设置")
        output_layout = QVBoxLayout(output_group)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("输出格式："))
        self._format_combo = QComboBox()
        self._format_combo.addItem("TXT — 纯文本", "txt")
        self._format_combo.addItem("PDF — 可搜索 PDF", "pdf")
        self._format_combo.addItem("Word — 保留版面结构", "word")
        self._format_combo.addItem("HTML — 网页格式", "html")
        self._format_combo.addItem("Excel — 表格数据", "excel")
        self._format_combo.addItem("RTF — 富文本格式", "rtf")
        self._format_combo.setFixedWidth(280)
        fmt_row.addWidget(self._format_combo)
        fmt_row.addStretch()
        output_layout.addLayout(fmt_row)

        self._preserve_layout_check = QCheckBox("TXT/RTF 保留版面结构（使用 PPStructureV3）")
        self._preserve_layout_check.setToolTip("勾选后 TXT/RTF 导出也会走结构化解析以保留段落层次")
        output_layout.addWidget(self._preserve_layout_check)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("输出目录："))
        self._output_dir = QLineEdit()
        from app.utils.paths import default_output_dir
        self._output_dir.setText(str(default_output_dir()))
        dir_row.addWidget(self._output_dir)
        dir_browse = QPushButton("选择")
        dir_browse.setFixedWidth(60)
        dir_browse.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(dir_browse)
        output_layout.addLayout(dir_row)

        main_layout.addWidget(output_group)

        # ── 开始按钮 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._start_btn = QPushButton("开始高级转换")
        self._start_btn.setObjectName("startButton")
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self._start_btn)
        main_layout.addLayout(btn_row)

        main_layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "",
            "支持的文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.pdf);;所有文件 (*)",
        )
        if path:
            self._file_path.setText(path)
            self._start_btn.setEnabled(True)

    def _browse_output_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self._output_dir.setText(d)

    def _on_start(self) -> None:
        params = {
            "file_path": Path(self._file_path.text()),
            "pipeline": self._pipeline_combo.currentData(),
            "language": self._lang_combo.currentData(),
            "output_format": self._format_combo.currentData(),
            "use_doc_orientation_classify": self._orientation_check.isChecked(),
            "use_doc_unwarping": self._unwarp_check.isChecked(),
            "use_textline_orientation": self._textline_ori_check.isChecked(),
            "render_dpi": self._dpi_spin.value(),
            "preserve_layout": self._preserve_layout_check.isChecked(),
            "output_dir": Path(self._output_dir.text()),
        }
        self.start_requested.emit(params)
