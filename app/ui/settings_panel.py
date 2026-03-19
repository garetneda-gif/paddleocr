"""设置面板 — 默认配置、模型缓存管理、关于。"""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal as _Signal, QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ACCENT, DANGER, TEXT_PRIMARY, TEXT_SECONDARY, __version__
from app.utils.language_map import LANGUAGES
from app.utils.paths import default_output_dir

_PADDLEX_CACHE = Path.home() / ".paddlex" / "official_models"


def _find_model_dirs() -> list[tuple[str, Path]]:
    """返回所有实际存在的模型目录 [(label, path), ...]。"""
    dirs: list[tuple[str, Path]] = []
    try:
        from app.core.onnx_engine import _find_onnx_dir
        onnx_dir = _find_onnx_dir()
        if onnx_dir:
            dirs.append(("ONNX 模型", onnx_dir))
    except Exception:
        pass
    if _PADDLEX_CACHE.exists():
        dirs.append(("PaddleX 缓存", _PADDLEX_CACHE))
    return dirs


class _CacheInfoWorker(QThread):
    """后台计算模型缓存大小。"""

    finished = _Signal(str)

    def run(self):
        dirs = _find_model_dirs()
        if not dirs:
            self.finished.emit("未找到模型目录")
            return

        lines: list[str] = []
        total_size = 0
        total_models = 0
        for label, d in dirs:
            try:
                models = [p for p in d.iterdir() if p.is_dir() or p.suffix == ".onnx"]
                size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                total_size += size
                total_models += len(models)
                lines.append(f"{label}：{d}")
            except Exception:
                lines.append(f"{label}：读取失败")

        size_mb = total_size / (1024 * 1024)
        lines.append(f"已缓存模型：{total_models} 个")
        lines.append(f"占用空间：{size_mb:.0f} MB")
        self.finished.emit("\n".join(lines))


class SettingsPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = QSettings("PaddleOCR", "Desktop")
        self._cache_worker: _CacheInfoWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("设置")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        # ── 默认语言 ──
        lang_group = QGroupBox("默认识别语言")
        lang_layout = QHBoxLayout(lang_group)
        self._lang_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self._lang_combo.addItem(f"{name} ({code})", code)
        self._lang_combo.setFixedWidth(280)

        # 从 QSettings 恢复
        saved_lang = self._settings.value("ocr/language", "ch")
        idx = self._lang_combo.findData(saved_lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        self._lang_combo.currentIndexChanged.connect(self._save_language)

        lang_layout.addWidget(self._lang_combo)
        lang_layout.addStretch()
        layout.addWidget(lang_group)

        # ── 默认输出目录 ──
        dir_group = QGroupBox("默认输出目录")
        dir_layout = QHBoxLayout(dir_group)

        saved_dir = self._settings.value("output/directory", "")
        self._dir_edit = QLineEdit(saved_dir or str(default_output_dir()))
        self._dir_edit.editingFinished.connect(self._save_directory)
        dir_layout.addWidget(self._dir_edit)

        dir_btn = QPushButton("选择")
        dir_btn.setFixedWidth(60)
        dir_btn.clicked.connect(self._browse_dir)
        dir_layout.addWidget(dir_btn)
        open_btn = QPushButton("打开")
        open_btn.setFixedWidth(60)
        open_btn.clicked.connect(self._open_dir)
        dir_layout.addWidget(open_btn)
        layout.addWidget(dir_group)

        # ── 模型缓存 ──
        cache_group = QGroupBox("模型缓存")
        cache_layout = QVBoxLayout(cache_group)

        self._cache_info = QLabel("正在计算...")
        cache_layout.addWidget(self._cache_info)

        cache_btn_row = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self._update_cache_info)
        cache_btn_row.addWidget(refresh_btn)

        clear_btn = QPushButton("删除 PaddleX 模型")
        clear_btn.setFixedWidth(140)
        clear_btn.setStyleSheet(f"color: {DANGER};")
        clear_btn.clicked.connect(self._clear_cache)
        cache_btn_row.addWidget(clear_btn)
        cache_btn_row.addStretch()
        cache_layout.addLayout(cache_btn_row)

        layout.addWidget(cache_group)

        # ── 关于 ──
        about_group = QGroupBox("关于")
        about_layout = QVBoxLayout(about_group)
        about_text = QLabel(
            f"PaddleOCR 桌面版 v{__version__}\n\n"
            "识别引擎：ONNX Runtime（PP-OCRv5）+ 可选 PaddlePaddle（PPStructureV3）\n"
            "UI 框架：PySide6 (Qt 6)\n\n"
            "支持格式：TXT / PDF / Word / HTML / Excel / RTF"
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet(f"color: {TEXT_SECONDARY}; line-height: 1.5;")
        about_layout.addWidget(about_text)
        layout.addWidget(about_group)

        layout.addStretch()

        # 异步加载缓存信息
        self._update_cache_info()

    def _save_language(self) -> None:
        self._settings.setValue("ocr/language", self._lang_combo.currentData())

    def _save_directory(self) -> None:
        self._settings.setValue("output/directory", self._dir_edit.text())

    def _browse_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择默认输出目录")
        if d:
            self._dir_edit.setText(d)
            self._save_directory()

    def _open_dir(self) -> None:
        import subprocess, sys
        path = self._dir_edit.text()
        if sys.platform == "darwin":
            subprocess.run(["open", path])

    def _update_cache_info(self) -> None:
        self._cache_info.setText("正在计算...")
        self._cache_worker = _CacheInfoWorker(self)
        self._cache_worker.finished.connect(self._on_cache_info_ready)
        self._cache_worker.start()

    def _on_cache_info_ready(self, text: str) -> None:
        self._cache_info.setText(text)
        self._cache_worker = None

    def _clear_cache(self) -> None:
        # 计算目录大小，让用户知道要删多少
        size_mb = 0
        if _PADDLEX_CACHE.exists():
            size_mb = sum(
                f.stat().st_size for f in _PADDLEX_CACHE.rglob("*") if f.is_file()
            ) / (1024 * 1024)

        reply = QMessageBox.warning(
            self, "⚠️ 删除模型文件",
            f"即将永久删除 PaddleX 模型文件（{size_mb:.0f} MB）：\n"
            f"  {_PADDLEX_CACHE}\n\n"
            "删除后使用 PaddlePaddle 引擎时需要重新下载模型。\n"
            "ONNX 模型不受影响。\n\n"
            "确定要删除吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if _PADDLEX_CACHE.exists():
                shutil.rmtree(_PADDLEX_CACHE)
                _PADDLEX_CACHE.mkdir(parents=True, exist_ok=True)
            self._update_cache_info()
            QMessageBox.information(self, "已删除", "PaddleX 模型文件已删除。下次使用时将重新下载。")

    def get_output_dir(self) -> str:
        """供外部读取当前输出目录。"""
        return self._dir_edit.text()
