"""PaddleOCR 桌面应用入口。"""

import os
import sys

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("PaddleOCR")
    app.setApplicationDisplayName("PaddleOCR — 智能文档识别")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
