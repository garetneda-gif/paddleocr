"""子进程 OCR — 批量处理 + 并行支持，退出后 OS 回收所有内存。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

BATCH_SIZE = 50


def _subprocess_batch_worker(args_json: str) -> str:
    """子进程入口：批量 OCR，返回 JSON 结果文件路径。"""
    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["OPENBLAS_NUM_THREADS"] = "2"
    os.environ["MKL_NUM_THREADS"] = "2"
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

    args = json.loads(args_json)
    image_paths = args["image_paths"]
    lang = args["lang"]
    speed_mode = args["speed_mode"]
    out_path = args["out_path"]

    try:
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

    return out_path


def run_ocr_batch(image_paths: list[Path], lang: str, speed_mode: str) -> list[dict]:
    """单批次子进程 OCR（兼容旧接口）。"""
    return run_ocr_parallel([image_paths], lang, speed_mode, max_workers=1)[0]


def run_ocr_parallel(
    batches: list[list[Path]], lang: str, speed_mode: str, max_workers: int = 2
) -> list[list[dict]]:
    """并行多批次 OCR，每个批次在独立子进程中运行。

    Args:
        batches: [[page1, page2, ...], [page3, page4, ...], ...]
        max_workers: 同时运行的子进程数

    Returns:
        [[{texts, blocks}, ...], [...], ...]  与 batches 一一对应
    """
    import multiprocessing as mp

    # 准备每个批次的参数
    task_args = []
    for batch in batches:
        out_path = tempfile.mktemp(suffix=".json", prefix="pocr_res_")
        args = {
            "image_paths": [str(p) for p in batch],
            "lang": lang,
            "speed_mode": speed_mode,
            "out_path": out_path,
        }
        task_args.append(json.dumps(args))

    # 用 spawn context 的 ProcessPoolExecutor 并行执行
    ctx = mp.get_context("spawn")
    results_by_batch: list[list[dict]] = []

    with ProcessPoolExecutor(
        max_workers=min(max_workers, len(batches)),
        mp_context=ctx,
    ) as pool:
        futures = list(pool.map(_subprocess_batch_worker, task_args, timeout=600))

    for out_path in futures:
        p = Path(out_path)
        if not p.exists():
            results_by_batch.append([{"error": "子进程未产生结果"}])
            continue
        raw = json.loads(p.read_text())
        p.unlink(missing_ok=True)
        if isinstance(raw, dict) and "error" in raw:
            results_by_batch.append([raw])
        else:
            results_by_batch.append(raw)

    return results_by_batch
