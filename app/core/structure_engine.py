"""结构化引擎封装 — 将 PPStructureV3 原始输出标准化为 DocumentResult。

注意：此模块依赖 PaddlePaddle + paddleocr，仅在安装了这些包时可用。
ONNX-only 模式下此模块不会被导入。
"""

from __future__ import annotations

import os
from pathlib import Path

from app.models import BlockResult, BlockType, DocumentResult, PageResult

# PPStructureV3 layout label -> BlockType 映射
_LABEL_MAP: dict[str, BlockType] = {
    "title": BlockType.TITLE,
    "text": BlockType.PARAGRAPH,
    "table": BlockType.TABLE,
    "figure": BlockType.FIGURE,
    "figure_caption": BlockType.CAPTION,
    "table_caption": BlockType.CAPTION,
    "header": BlockType.OTHER,
    "footer": BlockType.OTHER,
    "reference": BlockType.PARAGRAPH,
    "equation": BlockType.FORMULA,
    "formula": BlockType.FORMULA,
    "list": BlockType.LIST,
    "abstract": BlockType.PARAGRAPH,
    "content": BlockType.PARAGRAPH,
}


class StructureEngine:
    """封装 PPStructureV3，提供统一的 predict -> DocumentResult 接口。"""

    def __init__(
        self,
        lang: str = "ch",
        options: dict[str, object] | None = None,
    ) -> None:
        self._lang = lang
        self._options = {k: v for k, v in (options or {}).items() if v is not None}
        self._pipeline = None

    def _ensure_model(self) -> None:
        if self._pipeline is not None:
            return
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

        # PyInstaller 打包后 importlib.metadata 查不到包版本，
        # 导致 paddlex 的依赖检查误判为缺失。直接跳过。
        try:
            import paddlex.utils.deps as _pdx_deps
            _pdx_deps.is_extra_available = lambda *a, **k: True
            _pdx_deps.require_extra = lambda *a, **k: None
            _pdx_deps.is_dep_available = lambda *a, **k: True
            _pdx_deps.require_deps = lambda *a, **k: None
        except Exception:
            pass

        from paddleocr import PPStructureV3

        kwargs = dict(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_table_recognition=True,
            use_formula_recognition=False,
            use_chart_recognition=False,
            use_seal_recognition=False,
            use_region_detection=True,
            lang=self._lang,
        )
        kwargs.update(self._options)
        self._pipeline = PPStructureV3(**kwargs)

    def predict(self, image_path: Path) -> DocumentResult:
        self._ensure_model()
        raw_results = self._pipeline.predict(str(image_path))

        pages: list[PageResult] = []
        all_texts: list[str] = []

        for page_raw in raw_results:
            if page_raw is None:
                continue

            page_idx = page_raw.get("page_index", len(pages))
            width = page_raw.get("width", 0)
            height = page_raw.get("height", 0)

            blocks: list[BlockResult] = []

            # 优先从 overall_ocr_res 提取行级 block（每行独立 bbox），
            # 对齐开源项目做法，确保 PDF 文本层逐行精确定位。
            # 回退：overall_ocr_res 不可用时，从 parsing_res_list 提取段落级 block。
            overall_ocr = page_raw.get("overall_ocr_res") or {}
            rec_boxes = overall_ocr.get("rec_boxes", [])
            rec_texts = overall_ocr.get("rec_texts", [])
            rec_scores = overall_ocr.get("rec_scores", [])

            if hasattr(rec_boxes, "tolist"):
                rec_boxes = rec_boxes.tolist()

            if rec_texts:
                for i, text in enumerate(rec_texts):
                    if not text or not text.strip():
                        continue
                    box = rec_boxes[i] if i < len(rec_boxes) else [0, 0, 0, 0]
                    score = float(rec_scores[i]) if i < len(rec_scores) else None
                    bbox = (
                        float(box[0]),
                        float(box[1]),
                        float(box[2]),
                        float(box[3]),
                    )
                    blocks.append(
                        BlockResult(
                            block_type=BlockType.PARAGRAPH,
                            bbox=bbox,
                            text=text,
                            confidence=score,
                        )
                    )
                    all_texts.append(text)
            else:
                # 回退：从 parsing_res_list 提取段落级 block
                parsing_list = page_raw.get("parsing_res_list", [])
                for item in parsing_list:
                    label = getattr(item, "label", "other")
                    block_type = _LABEL_MAP.get(label, BlockType.OTHER)

                    raw_bbox = getattr(item, "bbox", [0, 0, 0, 0])
                    bbox = (
                        float(raw_bbox[0]),
                        float(raw_bbox[1]),
                        float(raw_bbox[2]),
                        float(raw_bbox[3]),
                    )

                    content = getattr(item, "content", "") or ""

                    blocks.append(
                        BlockResult(
                            block_type=block_type,
                            bbox=bbox,
                            text=content,
                        )
                    )
                    if content:
                        all_texts.append(content)

            # 补充表格结果
            for tbl in page_raw.get("table_res_list", []):
                if not isinstance(tbl, dict):
                    continue
                html = tbl.get("html", "")
                cell_data = tbl.get("cell_data")
                coord = tbl.get("bbox", tbl.get("coordinate", [0, 0, 0, 0]))
                bbox = (
                    float(coord[0]),
                    float(coord[1]),
                    float(coord[2]),
                    float(coord[3]),
                )
                blocks.append(
                    BlockResult(
                        block_type=BlockType.TABLE,
                        bbox=bbox,
                        text="",
                        html=html if html else None,
                        table_cells=cell_data,
                    )
                )

            pages.append(
                PageResult(
                    page_index=page_idx,
                    width=int(width),
                    height=int(height),
                    blocks=blocks,
                )
            )

        return DocumentResult(
            source_path=image_path,
            page_count=len(pages),
            pages=pages,
            plain_text="\n".join(all_texts),
        )
