"""ONNX OCR 能力测试。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import app.core.onnx_engine as onnx_engine


def test_resolve_ocr_backend_prefers_onnx_for_supported_language(monkeypatch):
    monkeypatch.setattr(onnx_engine, "onnx_available", lambda speed_mode="mobile": True)
    monkeypatch.setattr(onnx_engine, "paddle_available", lambda: False)

    assert onnx_engine.resolve_ocr_backend("ch", "mobile") == "onnx"
    assert onnx_engine.resolve_ocr_backend("en", "server") == "onnx"


def test_resolve_ocr_backend_falls_back_to_paddle_for_unsupported_language(monkeypatch):
    monkeypatch.setattr(onnx_engine, "onnx_available", lambda speed_mode="mobile": True)
    monkeypatch.setattr(onnx_engine, "paddle_available", lambda: True)

    assert onnx_engine.resolve_ocr_backend("japan", "mobile") == "paddle"


def test_resolve_ocr_backend_raises_when_language_unsupported_and_no_paddle(monkeypatch):
    monkeypatch.setattr(onnx_engine, "onnx_available", lambda speed_mode="mobile": True)
    monkeypatch.setattr(onnx_engine, "paddle_available", lambda: False)

    with pytest.raises(RuntimeError, match="仅支持中文和英文"):
        onnx_engine.resolve_ocr_backend("japan", "mobile")
