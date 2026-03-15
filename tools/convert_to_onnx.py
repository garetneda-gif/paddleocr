"""
PaddleOCR PP-OCRv5 → ONNX 转换脚本

将 PP-OCRv5 mobile/server 检测+识别模型转换为 ONNX，
输出到 /Volumes/MOVESPEED/存储/models/onnx/<model_name>.onnx

文件名对应关系（与 onnx_engine.py 的 _MODEL_FILES 一致）：
    PP-OCRv5_mobile_det.onnx
    PP-OCRv5_mobile_rec.onnx
    PP-OCRv5_server_det.onnx
    PP-OCRv5_server_rec.onnx

用法（请在自己的终端里运行，不要通过 Claude Code）：
    cd /Users/jikunren/Documents/paddleocr
    source .venv/bin/activate
    python tools/convert_to_onnx.py [--models mobile|server|all]

依赖：
    paddle2onnx >= 2.0
    paddlepaddle >= 3.0
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ["FLAGS_call_stack_level"] = "0"
os.environ["OMP_NUM_THREADS"] = "2"

# 原始 Paddle 模型存储目录（各子目录含 inference.json + inference.pdiparams）
MODEL_ROOT = Path("/Volumes/MOVESPEED/存储/models")
# ONNX 输出目录（与 onnx_engine.py 的 _EXTERNAL_ONNX_DIR 一致）
ONNX_OUT_DIR = MODEL_ROOT / "onnx"

# 模型名 → 输出 ONNX 文件名（与 onnx_engine._MODEL_FILES 保持一致）
MODELS: dict[str, dict] = {
    "PP-OCRv5_mobile_det": {"type": "det", "onnx_name": "PP-OCRv5_mobile_det.onnx"},
    "PP-OCRv5_server_det": {"type": "det", "onnx_name": "PP-OCRv5_server_det.onnx"},
    "PP-OCRv5_mobile_rec": {"type": "rec", "onnx_name": "PP-OCRv5_mobile_rec.onnx"},
    "PP-OCRv5_server_rec": {"type": "rec", "onnx_name": "PP-OCRv5_server_rec.onnx"},
}

MOBILE_SET = {"PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec"}
SERVER_SET = {"PP-OCRv5_server_det", "PP-OCRv5_server_rec"}


# ─────────────────────────────────────────────
# 1. 确保模型已下载
# ─────────────────────────────────────────────

def ensure_downloaded(model_names: list[str]) -> None:
    """检查模型文件是否已存在于外置硬盘。"""
    for name in model_names:
        model_dir = MODEL_ROOT / name
        if not model_dir.exists():
            print(f"[警告] 模型目录不存在: {model_dir}")
        else:
            model_file = model_dir / "inference.json"
            params_file = model_dir / "inference.pdiparams"
            if model_file.exists() and params_file.exists():
                size = params_file.stat().st_size / 1024 / 1024
                print(f"[OK] {name} ({size:.1f} MB params)")
            else:
                print(f"[警告] {name} 模型文件不完整")


# ─────────────────────────────────────────────
# 2. 找到模型文件
# ─────────────────────────────────────────────

def _find_model_files(model_dir: Path) -> tuple[Path | None, Path | None]:
    """
    在 model_dir 中查找静态推理模型文件。
    PaddlePaddle 3.x 新格式：inference.json + inference.pdiparams
    PaddlePaddle 旧格式：inference.pdmodel + inference.pdiparams
    返回 (model_file, params_file)
    """
    # 新格式 (PIR JSON)
    json_file = model_dir / "inference.json"
    params_file = model_dir / "inference.pdiparams"
    if json_file.exists() and params_file.exists():
        return json_file, params_file

    # 旧格式
    pdmodel = model_dir / "inference.pdmodel"
    if pdmodel.exists() and params_file.exists():
        return pdmodel, params_file

    # 扫描
    for f in model_dir.rglob("*.json"):
        p = f.with_suffix(".pdiparams")
        if p.exists():
            return f, p
    for f in model_dir.rglob("*.pdmodel"):
        p = f.with_suffix("").with_suffix("").parent / (f.stem + ".pdiparams")
        alt = f.parent / "inference.pdiparams"
        if p.exists():
            return f, p
        if alt.exists():
            return f, alt

    return None, None


# ─────────────────────────────────────────────
# 3. 转换单个模型
# ─────────────────────────────────────────────

def convert_model(model_name: str, opset: int = 11) -> bool:
    """
    将 model_name 对应的 Paddle 模型转换为 ONNX，
    输出到 ONNX_OUT_DIR/<onnx_name>（与 onnx_engine._MODEL_FILES 一致）。
    返回是否成功。
    """
    onnx_name = MODELS[model_name]["onnx_name"]
    onnx_path = ONNX_OUT_DIR / onnx_name

    if onnx_path.exists():
        size_mb = onnx_path.stat().st_size / 1024 / 1024
        print(f"[跳过] {onnx_name}: 已存在 ({size_mb:.1f} MB)")
        return True

    model_dir = MODEL_ROOT / model_name
    if not model_dir.exists():
        print(f"[错误] 模型目录不存在: {model_dir}")
        return False

    model_file, params_file = _find_model_files(model_dir)
    if model_file is None:
        print(f"[错误] 在 {model_dir} 中未找到推理模型文件")
        for f in sorted(model_dir.rglob("*")):
            print(f"         {f.relative_to(model_dir)}")
        return False

    ONNX_OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[转换] {model_name} → {onnx_name}")
    print(f"       模型: {model_file.name}  参数: {params_file.name}")
    print(f"       输出: {onnx_path}")

    try:
        import paddle2onnx
        paddle2onnx.export(
            model_filename=str(model_file),
            params_filename=str(params_file),
            save_file=str(onnx_path),
            opset_version=opset,
            enable_onnx_checker=True,
            optimize_tool="None",
            deploy_backend="onnxruntime",
        )
        size_mb = onnx_path.stat().st_size / 1024 / 1024
        print(f"[完成] {onnx_name}  {size_mb:.1f} MB\n")
        return True
    except Exception as e:
        print(f"[失败] {model_name}: {e}\n")
        if onnx_path.exists():
            onnx_path.unlink()
        return False


# ─────────────────────────────────────────────
# 4. 创建 inference.yml（如果不存在）
# ─────────────────────────────────────────────

DET_YML_TEMPLATE = """\
PostProcess:
  thresh: 0.3
  box_thresh: 0.6
  unclip_ratio: 1.5
  max_candidates: 1000
"""

REC_YML_TEMPLATE = """\
PostProcess:
  character_dict: {char_list}
"""


def ensure_yml(model_name: str) -> None:
    """新版 onnx_engine 不再读 inference.yml，此函数保留仅供参考。"""
    pass  # 字符字典改由 ppocr_keys_v5.txt 统一提供


# ─────────────────────────────────────────────
# 5. 验证 ONNX 推理
# ─────────────────────────────────────────────

def verify_onnx(model_name: str) -> bool:
    """用随机输入验证 ONNX 模型能跑通。"""
    import numpy as np
    import onnxruntime as ort

    onnx_name = MODELS[model_name]["onnx_name"]
    onnx_path = ONNX_OUT_DIR / onnx_name
    if not onnx_path.exists():
        return False

    try:
        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        inp = sess.get_inputs()[0]
        # 构造合法的随机输入（处理动态维度）
        shape = []
        for d in inp.shape:
            if isinstance(d, int) and d > 0:
                shape.append(d)
            elif MODELS[model_name]["type"] == "rec":
                shape.append({"batch": 1, "height": 48, "width": 320}.get(
                    str(d), 1 if len(shape) == 0 else (48 if len(shape) == 2 else 320)
                ))
            else:
                shape.append(1 if len(shape) == 0 else (3 if len(shape) == 1 else 32))
        dummy = np.random.randn(*shape).astype(np.float32)
        sess.run(None, {inp.name: dummy})
        print(f"[验证] {onnx_name}: ONNX 推理正常 ✓")
        return True
    except Exception as e:
        print(f"[验证] {onnx_name}: ONNX 推理失败 — {e}")
        return False


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="PaddleOCR → ONNX 模型转换")
    parser.add_argument(
        "--models",
        choices=["mobile", "server", "all"],
        default="mobile",
        help="要转换的模型集 (default: mobile)",
    )
    parser.add_argument("--opset", type=int, default=11, help="ONNX opset version")
    parser.add_argument("--no-download", action="store_true", help="跳过下载步骤")
    args = parser.parse_args()

    if args.models == "mobile":
        target_models = list(MOBILE_SET)
    elif args.models == "server":
        target_models = list(SERVER_SET)
    else:
        target_models = list(MOBILE_SET | SERVER_SET)

    # 检查外置硬盘
    if not MODEL_ROOT.exists():
        print(f"错误：外置硬盘未挂载: {MODEL_ROOT}")
        print("请插入 MOVESPEED 硬盘后重试。")
        sys.exit(1)

    print("=" * 60)
    print(f"PP-OCRv5 → ONNX 转换  ({args.models})")
    print(f"目标模型: {sorted(target_models)}")
    print(f"源目录:   {MODEL_ROOT}")
    print(f"输出目录: {ONNX_OUT_DIR}")
    print("=" * 60 + "\n")

    # 检查源模型文件
    ensure_downloaded(target_models)
    print()

    # 转换 + 验证
    results = {}
    for name in sorted(target_models):
        ok = convert_model(name, opset=args.opset)
        if ok:
            verify_onnx(name)
        results[name] = ok

    # 汇总
    print("\n" + "=" * 60)
    print("转换结果汇总")
    print("=" * 60)
    for name, ok in sorted(results.items()):
        status = "✓ 成功" if ok else "✗ 失败"
        onnx_name = MODELS[name]["onnx_name"]
        print(f"  {status}  {onnx_name}")

    if all(results.values()):
        print(f"\n所有模型转换完成！ONNX 文件已保存到: {ONNX_OUT_DIR}")
    else:
        print("\n部分模型转换失败，请检查上方日志。")
        sys.exit(1)


if __name__ == "__main__":
    main()
