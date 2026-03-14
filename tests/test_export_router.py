"""ExportRouter 单元测试 — 纯逻辑测试，不依赖 PaddleOCR。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.converters.base_converter import BaseConverter
from app.core.export_router import ExportRouter, create_default_router
from app.models.enums import OutputFormat


class DummyConverter(BaseConverter):
    def convert(self, result, output_path) -> None:
        pass


def test_register_and_select():
    router = ExportRouter()
    converter = DummyConverter()
    router.register(OutputFormat.TXT, converter)
    assert router.select_converter(OutputFormat.TXT) is converter


def test_select_unregistered_raises():
    router = ExportRouter()
    with pytest.raises(ValueError, match="No converter registered"):
        router.select_converter(OutputFormat.WORD)


def test_supported_formats():
    router = ExportRouter()
    router.register(OutputFormat.TXT, DummyConverter())
    router.register(OutputFormat.PDF, DummyConverter())
    assert set(router.supported_formats) == {OutputFormat.TXT, OutputFormat.PDF}


def test_default_router_has_all_formats():
    router = create_default_router()
    for fmt in OutputFormat:
        converter = router.select_converter(fmt)
        assert converter is not None
