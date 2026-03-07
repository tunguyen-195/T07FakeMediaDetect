from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
from flask import Flask, jsonify, request

from feature_runtime import FEATURE_WIDTHS, extract_feature_sets

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parents[1]
MODELS_ROOT = PROJECT_ROOT / "models"
ACTIVE_RELEASE_PATH = MODELS_ROOT / "active_benford_release.json"
MANIFEST_PATH = APP_ROOT / "model_manifest.json"
MODEL_NAME = "BenfordRichSVM"
APP = Flask(__name__)
MODEL = None
SCALER = None
METADATA: Dict[str, Any] | None = None
ACTIVE_RELEASE: Dict[str, Any] | None = None


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sanitize_request_id(value: str | None) -> str:
    if not value:
        return f"req_{int(time.time() * 1000)}"
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return cleaned[:120] or f"req_{int(time.time() * 1000)}"


def _resolve_models_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return MODELS_ROOT / candidate


def _load_active_release() -> Dict[str, Any]:
    if not ACTIVE_RELEASE_PATH.exists():
        raise FileNotFoundError(f"Benford active release missing: {ACTIVE_RELEASE_PATH}")
    manifest = _load_json(ACTIVE_RELEASE_PATH)
    required = [
        "release_id",
        "model_path",
        "scaler_path",
        "metadata_path",
        "metrics_path",
        "activated_at",
    ]
    missing = [key for key in required if not manifest.get(key)]
    if missing:
        raise ValueError(f"Benford active release missing keys: {missing}")
    resolved = dict(manifest)
    for key in ["model_path", "scaler_path", "metadata_path", "metrics_path"]:
        resolved[key] = _resolve_models_path(manifest[key])
        if resolved[key] is None or not resolved[key].exists():
            raise FileNotFoundError(f"Benford release path missing: {key} -> {manifest[key]}")
    return resolved


def _validate_metadata(metadata: Dict[str, Any], scaler) -> None:
    if metadata.get("feature_schema_version") != "benford_rich_v1":
        raise ValueError(
            "feature_schema_version mismatch: "
            f"{metadata.get('feature_schema_version')} != benford_rich_v1"
        )
    feature_width = int(metadata.get("feature_widths", {}).get("benford_rich", -1))
    if feature_width != 111:
        raise ValueError(f"benford_rich feature width mismatch: {feature_width} != 111")
    feature_order = metadata.get("feature_groups", {}).get("benford_rich") or metadata.get("feature_order")
    if not isinstance(feature_order, list) or len(feature_order) != 111:
        raise ValueError("benford_rich feature_order invalid or not length 111")
    scaler_width = getattr(scaler, "n_features_in_", None)
    if scaler_width != 111:
        raise ValueError(f"scaler feature width mismatch: {scaler_width} != 111")


def load_runtime_once():
    global MODEL, SCALER, METADATA, ACTIVE_RELEASE
    if MODEL is not None and SCALER is not None and METADATA is not None and ACTIVE_RELEASE is not None:
        return MODEL, SCALER, METADATA, ACTIVE_RELEASE

    ACTIVE_RELEASE = _load_active_release()
    MODEL = joblib.load(ACTIVE_RELEASE["model_path"])
    SCALER = joblib.load(ACTIVE_RELEASE["scaler_path"])
    METADATA = _load_json(ACTIVE_RELEASE["metadata_path"])
    _validate_metadata(METADATA, SCALER)
    return MODEL, SCALER, METADATA, ACTIVE_RELEASE


def _score_image(image_path: str) -> Dict[str, Any]:
    model, scaler, metadata, active_release = load_runtime_once()
    feature_sets = extract_feature_sets(image_path)
    vector = feature_sets["benford_rich"]
    if int(vector.shape[0]) != FEATURE_WIDTHS["benford_rich"]:
        raise ValueError(
            f"benford_rich vector width mismatch: {int(vector.shape[0])} != {FEATURE_WIDTHS['benford_rich']}"
        )
    scaled = scaler.transform(vector.reshape(1, -1))
    probs = model.predict_proba(scaled)[0]
    forged_score = float(probs[1])
    label = "Forged" if forged_score >= 0.5 else "Authentic"
    confidence = forged_score if label == "Forged" else (1.0 - forged_score)
    return {
        "forged_score": round(forged_score, 6),
        "label": label,
        "confidence": round(confidence * 100.0, 2),
        "feature_width": int(vector.shape[0]),
        "feature_schema_version": metadata["feature_schema_version"],
        "release_id": active_release["release_id"],
        "model_name": MODEL_NAME,
    }


@APP.get("/health")
def health():
    try:
        _model, _scaler, metadata, active_release = load_runtime_once()
        return jsonify(
            {
                "ok": True,
                "model_name": MODEL_NAME,
                "release_id": active_release["release_id"],
                "feature_schema_version": metadata["feature_schema_version"],
                "feature_width": metadata["feature_widths"]["benford_rich"],
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@APP.post("/predict/image")
def predict_image():
    started = time.time()
    payload = request.get_json(silent=True) or {}
    image_path = payload.get("image_path")
    request_id = _sanitize_request_id(payload.get("request_id"))
    source_type = payload.get("source_type") or "image"

    if not image_path:
        return jsonify({"ok": False, "error": "image_path is required"}), 400
    if not os.path.exists(image_path):
        return jsonify({"ok": False, "error": f"image_path not found: {image_path}"}), 400

    try:
        result = _score_image(image_path)
        return jsonify(
            {
                "ok": True,
                "request_id": request_id,
                "source_type": source_type,
                "error": None,
                "latency_ms": round((time.time() - started) * 1000.0, 2),
                "mask_path": None,
                **result,
            }
        )
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "request_id": request_id,
                "source_type": source_type,
                "model_name": MODEL_NAME,
                "forged_score": None,
                "label": None,
                "confidence": None,
                "feature_width": None,
                "feature_schema_version": None,
                "release_id": None,
                "mask_path": None,
                "latency_ms": round((time.time() - started) * 1000.0, 2),
                "error": str(exc),
            }
        ), 500


if __name__ == "__main__":
    manifest = _load_json(MANIFEST_PATH)
    sidecar = manifest["sidecar"]
    APP.run(host=sidecar["host"], port=int(sidecar["port"]))
