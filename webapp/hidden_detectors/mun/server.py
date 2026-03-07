from __future__ import annotations

import json
import os
import re
import time
import importlib
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, request


APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parents[1]
MODELS_ROOT = PROJECT_ROOT / "models" / "hidden_detectors" / "mun"
WEIGHTS_ROOT = MODELS_ROOT / "weights"
OUTPUT_ROOT = MODELS_ROOT / "outputs"
MANIFEST_PATH = APP_ROOT / "model_manifest.json"
CONFIG_PATH = APP_ROOT / "mun_conf.py"

app = Flask(__name__)
MODEL = None
MODEL_NAME = "MUN"
DEVICE = "cpu"


CUSTOM_IMPORT_MODULES = [
    "mmseg.models.data_preprocessor",
    "mmseg.datasets.transforms.transforms",
    "mmseg.datasets.transforms.formatting",
    "mmseg.models.segmentors.npp",
    "mmseg.models.decode_heads.nu_head",
    "mmseg.models.losses.iou_loss",
    "mmpretrain.models.backbones.convnext",
]


def _load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _sanitize_request_id(value: str | None) -> str:
    if not value:
        return f"req_{int(time.time() * 1000)}"
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return cleaned[:120] or f"req_{int(time.time() * 1000)}"


def _ensure_paths() -> Dict[str, Path]:
    manifest = _load_manifest()
    checkpoint_path = WEIGHTS_ROOT / manifest["checkpoint"]["expected_file_name"]
    noiseprint_path = WEIGHTS_ROOT / manifest["noiseprint_checkpoint"]["expected_file_name"]
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"MUN checkpoint missing: {checkpoint_path}")
    if not noiseprint_path.exists():
        raise FileNotFoundError(f"NoisePrint++ checkpoint missing: {noiseprint_path}")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    return {
        "checkpoint_path": checkpoint_path,
        "noiseprint_path": noiseprint_path,
    }


def _ensure_custom_registrations() -> None:
    # Some Windows installs do not reliably execute config-level custom_imports
    # before the test pipeline is built. Import them explicitly so transforms like
    # NPPTest and NPPPackSegInputs are always registered.
    for module_name in CUSTOM_IMPORT_MODULES:
        importlib.import_module(module_name)


def _extract_probability_map(result):
    import torch

    if hasattr(result, "seg_logits") and getattr(result, "seg_logits", None) is not None:
        logits = result.seg_logits.data
        if logits.ndim == 3 and logits.shape[0] >= 2:
            probs = torch.softmax(logits.float(), dim=0)[1]
        else:
            probs = torch.sigmoid(logits.float()).squeeze(0)
    elif hasattr(result, "pred_sem_seg") and getattr(result, "pred_sem_seg", None) is not None:
        probs = result.pred_sem_seg.data.float().squeeze(0)
    else:
        raise RuntimeError("MUN inference result has no seg_logits or pred_sem_seg")

    if probs.ndim != 2:
        probs = probs.squeeze()
    return probs.clamp(0, 1)


def _save_probability_mask(prob_map, request_id: str) -> str:
    import numpy as np
    from PIL import Image

    mask_path = OUTPUT_ROOT / f"{request_id}.png"
    arr = (prob_map.cpu().numpy() * 255.0).clip(0, 255).astype(np.uint8)
    Image.fromarray(arr, mode="L").save(mask_path)
    return str(mask_path)


def _score_from_probability_map(prob_map) -> float:
    import torch

    flat = prob_map.reshape(-1)
    topk = max(1, int(flat.numel() * 0.01))
    values = torch.topk(flat, k=topk, sorted=False).values
    return float(values.mean().item())


def load_model_once():
    global MODEL, DEVICE
    if MODEL is not None:
        return MODEL

    paths = _ensure_paths()
    os.environ["T07_MUN_NPP_PATH"] = str(paths["noiseprint_path"])

    import torch
    from mmseg.apis import inference_model, init_model  # noqa: F401

    _ensure_custom_registrations()

    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    MODEL = init_model(str(CONFIG_PATH), str(paths["checkpoint_path"]), device=DEVICE)
    return MODEL


@app.get("/health")
def health():
    try:
        load_model_once()
        return jsonify(
            {
                "ok": True,
                "model_name": MODEL_NAME,
                "device": DEVICE,
                "weights_root": str(WEIGHTS_ROOT),
            }
        )
    except Exception as exc:  # pragma: no cover - runtime path
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/predict/image")
def predict_image():
    started = time.time()
    payload = request.get_json(silent=True) or {}
    image_path = payload.get("image_path")
    request_id = _sanitize_request_id(payload.get("request_id"))
    source_type = payload.get("source_type") or "image"

    if not image_path:
        return jsonify({"ok": False, "error": "image_path is required"}), 400

    try:
        load_model_once()
        _ensure_custom_registrations()
        from mmseg.apis import inference_model

        result = inference_model(MODEL, image_path)
        prob_map = _extract_probability_map(result)
        forged_score = _score_from_probability_map(prob_map)
        label = "Forged" if forged_score >= 0.5 else "Authentic"
        mask_path = _save_probability_mask(prob_map, request_id)
        latency_ms = round((time.time() - started) * 1000.0, 2)
        return jsonify(
            {
                "ok": True,
                "model_name": MODEL_NAME,
                "forged_score": round(forged_score, 6),
                "label": label,
                "mask_path": mask_path,
                "latency_ms": latency_ms,
                "error": None,
                "source_type": source_type,
            }
        )
    except Exception as exc:  # pragma: no cover - runtime path
        return jsonify(
            {
                "ok": False,
                "model_name": MODEL_NAME,
                "forged_score": None,
                "label": None,
                "mask_path": None,
                "latency_ms": round((time.time() - started) * 1000.0, 2),
                "error": str(exc),
                "source_type": source_type,
            }
        ), 500


if __name__ == "__main__":
    manifest = _load_manifest()
    host = manifest["sidecar"]["host"]
    port = int(manifest["sidecar"]["port"])
    app.run(host=host, port=port)
