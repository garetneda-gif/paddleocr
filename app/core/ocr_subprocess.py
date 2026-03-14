"""子进程 OCR — 批量处理后退出，OS 回收所有内存。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

BATCH_SIZE = 20  # 每个子进程处理的页数，之后退出释放内存


def _subprocess_batch_worker(
    image_paths_json: str, lang: str, speed_mode: str, out_path: str
) -> None:
    """子进程入口：批量 OCR 多页，结果写 JSON 文件。"""
    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["OPENBLAS_NUM_THREADS"] = "2"
    os.environ["MKL_NUM_THREADS"] = "2"
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

    try:
        image_paths = json.loads(image_paths_json)
        from paddleocr import PaddleOCR

        kwargs = dict(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            lang=lang,
        )
        if speed_mode == "mobile":
            kwargs["text_detection_model_name"] = "PP-OCRv5_mobile_det"
            kwargs["text_recognition_model_name"] = "PP-OCRv5_mobile_rec"

        ocr = PaddleOCR(**kwargs)

        all_results = []
        for img_path in image_paths:
            raw_results = list(ocr.predict(img_path))
            texts = []
            blocks = []
            for page_raw in raw_results:
                if page_raw is None:
                    continue
                rec_texts = page_raw.get("rec_texts", [])
                rec_scores = page_raw.get("rec_scores", [])
                rec_boxes = page_raw.get("rec_boxes", [])
                texts.extend(rec_texts)
                for i, (text, score) in enumerate(zip(rec_texts, rec_scores)):
                    bbox = [0, 0, 0, 0]
                    if i < len(rec_boxes) and rec_boxes[i] is not None:
                        b = rec_boxes[i]
                        bbox = [float(b[0]), float(b[1]), float(b[2]), float(b[3])]
                    blocks.append({"text": text, "score": float(score), "bbox": bbox})
            all_results.append({"texts": texts, "blocks": blocks})

        Path(out_path).write_text(json.dumps(all_results, ensure_ascii=False))
    except Exception as e:
        Path(out_path).write_text(json.dumps({"error": str(e)}))


def run_ocr_batch(image_paths: list[Path], lang: str, speed_mode: str) -> list[dict]:
    """在子进程中批量 OCR，完成后子进程退出释放所有内存。"""
    import multiprocessing as mp

    result_file = Path(tempfile.mktemp(suffix=".json", prefix="pocr_res_"))
    paths_json = json.dumps([str(p) for p in image_paths])

    ctx = mp.get_context("spawn")
    p = ctx.Process(
        target=_subprocess_batch_worker,
        args=(paths_json, lang, speed_mode, str(result_file)),
    )
    p.start()
    p.join(timeout=600)

    if p.is_alive():
        p.kill()
        p.join()
        return [{"error": "子进程超时"}]

    if p.exitcode != 0:
        return [{"error": f"子进程异常退出 (code={p.exitcode})"}]

    if not result_file.exists():
        return [{"error": "子进程未产生结果"}]

    raw = json.loads(result_file.read_text())
    result_file.unlink(missing_ok=True)

    if isinstance(raw, dict) and "error" in raw:
        return [raw]
    return raw
