"""导出路由 — 根据 OutputFormat 选择对应的 converter。"""

from __future__ import annotations

from app.converters.base_converter import BaseConverter
from app.models.enums import OutputFormat


class ExportRouter:
    """根据 OutputFormat 路由到正确的 converter 实例。"""

    def __init__(self) -> None:
        self._converters: dict[OutputFormat, BaseConverter] = {}

    def register(self, fmt: OutputFormat, converter: BaseConverter) -> None:
        self._converters[fmt] = converter

    def select_converter(self, fmt: OutputFormat) -> BaseConverter:
        converter = self._converters.get(fmt)
        if converter is None:
            raise ValueError(f"No converter registered for format: {fmt.value}")
        return converter

    @property
    def supported_formats(self) -> list[OutputFormat]:
        return list(self._converters.keys())


def create_default_router() -> ExportRouter:
    """创建预注册了所有导出器的路由实例。"""
    from app.converters.txt_converter import TxtConverter
    from app.converters.pdf_converter import PdfConverter
    from app.converters.rtf_converter import RtfConverter
    from app.converters.word_converter import WordConverter
    from app.converters.html_converter import HtmlConverter
    from app.converters.excel_converter import ExcelConverter

    router = ExportRouter()
    router.register(OutputFormat.TXT, TxtConverter())
    router.register(OutputFormat.PDF, PdfConverter())
    router.register(OutputFormat.RTF, RtfConverter())
    router.register(OutputFormat.WORD, WordConverter())
    router.register(OutputFormat.HTML, HtmlConverter())
    router.register(OutputFormat.EXCEL, ExcelConverter())
    return router
