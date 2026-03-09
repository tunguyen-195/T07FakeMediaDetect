from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

import cv2
import numpy as np
from flask import Flask, jsonify, request
from PIL import Image

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parents[1]
MODELS_ROOT = PROJECT_ROOT / "models" / "hidden_detectors" / "photoholmes"
OUTPUT_ROOT = MODELS_ROOT / "outputs"
MANIFEST_PATH = APP_ROOT / "model_manifest.json"

# Keep legacy backend names for compatibility with the app/runtime scripts.
SUPPORTED_BACKENDS = ("noiseprint", "comprint", "splicebuster", "noisesniffer")
CANONICAL_BACKEND = {
    "noiseprint": "splicebuster",
    "splicebuster": "splicebuster",
    "comprint": "noisesniffer",
    "noisesniffer": "noisesniffer",
}
MODEL_NAMES = {
    "noiseprint": "PhotoHolmesSplicebusterCPU",
    "splicebuster": "PhotoHolmesSplicebusterCPU",
    "comprint": "PhotoHolmesNoisesnifferCPU",
    "noisesniffer": "PhotoHolmesNoisesnifferCPU",
}

APP = Flask(__name__)
ACTIVE_BACKEND = "noiseprint"
ACTIVE_CANONICAL = "splicebuster"
ACTIVE_METHOD = None
ACTIVE_PREPROCESS = None
INIT_PAYLOAD: Dict[str, Any] = {
    "ok": False,
    "backend": ACTIVE_BACKEND,
    "engine": "photoholmes_upstream",
    "error": "not initialized",
}


def _load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _normalize_backend(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in SUPPORTED_BACKENDS:
        return raw
    return "noiseprint"


def _canonical_backend(backend: str) -> str:
    return CANONICAL_BACKEND.get(_normalize_backend(backend), "splicebuster")


def _parse_backend_url(env_name: str, default_host: str, default_port: int) -> Tuple[str, int]:
    raw = str(os.environ.get(env_name, "")).strip()
    if not raw:
        return default_host, default_port
    parsed = urlparse(raw)
    if parsed.scheme and parsed.hostname and parsed.port:
        return parsed.hostname, int(parsed.port)
    return default_host, default_port


def _resolve_host_port(backend: str) -> Tuple[str, int]:
    manifest = _load_manifest()
    sidecars = manifest.get("sidecars", {})
    # Public backend names for network ports remain noiseprint/comprint.
    sidecar_name = "noiseprint" if _canonical_backend(backend) == "splicebuster" else "comprint"
    backend_cfg = sidecars.get(sidecar_name, {})
    default_host = str(backend_cfg.get("host", "127.0.0.1"))
    default_port = int(backend_cfg.get("port", 8013 if sidecar_name == "noiseprint" else 8014))

    env_name = "T07_HIDDEN_DETECTOR_URL_NOISEPRINT" if sidecar_name == "noiseprint" else "T07_HIDDEN_DETECTOR_URL_COMPRINT"
    return _parse_backend_url(env_name, default_host, default_port)


def _sanitize_request_id(value: str | None) -> str:
    if not value:
        return f"req_{int(time.time() * 1000)}"
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return cleaned[:120] or f"req_{int(time.time() * 1000)}"


def _normalize_map(values: np.ndarray) -> np.ndarray:
    arr = np.nan_to_num(values.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    min_v = float(np.min(arr))
    max_v = float(np.max(arr))
    if max_v - min_v < 1e-8:
        return np.zeros_like(arr, dtype=np.float32)
    return ((arr - min_v) / (max_v - min_v)).astype(np.float32)


def _topk_mean(arr: np.ndarray, ratio: float = 0.02) -> float:
    flat = arr.reshape(-1)
    if flat.size == 0:
        return 0.0
    k = max(1, int(flat.size * ratio))
    if k >= flat.size:
        return float(np.mean(flat))
    part = np.partition(flat, flat.size - k)
    return float(np.mean(part[-k:]))


def _ensure_output_dir(backend: str) -> Path:
    out_dir = OUTPUT_ROOT / backend
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _save_mask(mask_norm: np.ndarray, backend: str, request_id: str) -> str:
    out_dir = _ensure_output_dir(backend)
    mask_img = (np.clip(mask_norm, 0.0, 1.0) * 255.0).astype(np.uint8)
    path = out_dir / f"{request_id}.png"
    Image.fromarray(mask_img, mode="L").save(path)
    return str(path)


def _load_image(path_str: str) -> np.ndarray:
    if not path_str:
        raise ValueError("image_path is required")
    image_path = Path(path_str)
    if not image_path.exists():
        raise FileNotFoundError(f"image_path not found: {image_path}")
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Unable to read image: {image_path}")
    return image


def _load_method(backend: str):
    canonical = _canonical_backend(backend)
    if canonical == "splicebuster":
        from photoholmes.methods.splicebuster import Splicebuster, splicebuster_preprocessing

        return canonical, Splicebuster(), splicebuster_preprocessing
    if canonical == "noisesniffer":
        from photoholmes.methods.noisesniffer import Noisesniffer, noisesniffer_preprocessing

        return canonical, Noisesniffer(), noisesniffer_preprocessing
    raise ValueError(f"Unsupported PhotoHolmes backend: {backend}")


def _extract_heatmap(raw_output: Any, canonical_backend: str) -> np.ndarray:
    if canonical_backend == "splicebuster":
        heatmap = np.asarray(raw_output, dtype=np.float32)
    else:
        # Noisesniffer returns (mask, painted_image)
        if isinstance(raw_output, tuple) and len(raw_output) >= 1:
            heatmap = np.asarray(raw_output[0], dtype=np.float32)
        else:
            heatmap = np.asarray(raw_output, dtype=np.float32)
    if heatmap.ndim == 3 and heatmap.shape[-1] == 1:
        heatmap = heatmap[:, :, 0]
    if heatmap.ndim != 2:
        raise RuntimeError(f"Unexpected heatmap shape from PhotoHolmes: {heatmap.shape}")
    return heatmap


def _analyze_image(image_bgr: np.ndarray) -> Tuple[float, np.ndarray]:
    if ACTIVE_METHOD is None or ACTIVE_PREPROCESS is None:
        raise RuntimeError("PhotoHolmes method is not initialized")

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    model_input = ACTIVE_PREPROCESS(image=image_rgb)
    raw_output = ACTIVE_METHOD.predict(**model_input)
    heatmap = _extract_heatmap(raw_output, ACTIVE_CANONICAL)
    mask_norm = _normalize_map(heatmap)
    score = float(np.clip(_topk_mean(mask_norm, ratio=0.02), 0.0, 1.0))
    return score, mask_norm


def _run_probe(backend: str) -> Dict[str, Any]:
    started = time.time()
    import_detail = ""
    method_name = ""
    try:
        import photoholmes  # type: ignore

        version = str(getattr(photoholmes, "__version__", "unknown"))
        import_detail = f"photoholmes=={version}"
    except Exception as exc:
        return {
            "ok": False,
            "backend": backend,
            "canonical_backend": _canonical_backend(backend),
            "engine": "photoholmes_upstream",
            "photoholmes_available": False,
            "photoholmes_detail": f"{type(exc).__name__}: {exc}",
            "method": None,
            "sample_score": None,
            "mask_valid": False,
            "latency_ms": round((time.time() - started) * 1000.0, 2),
            "error": "PhotoHolmes import failed",
        }

    try:
        canonical, method, preprocess = _load_method(backend)
        method_name = method.__class__.__name__
        rng = np.random.default_rng(20260309)
        synthetic = rng.integers(0, 256, size=(256, 384, 3), dtype=np.uint8)
        model_input = preprocess(image=synthetic)
        raw_output = method.predict(**model_input)
        heatmap = _extract_heatmap(raw_output, canonical)
        mask_norm = _normalize_map(heatmap)
        score = float(np.clip(_topk_mean(mask_norm, ratio=0.02), 0.0, 1.0))
        mask_valid = bool(mask_norm.shape == synthetic.shape[:2] and np.isfinite(mask_norm).all())
        ok = bool(np.isfinite(score) and mask_valid)
        error = None if ok else "analysis output invalid"
    except Exception as exc:
        canonical = _canonical_backend(backend)
        score = None
        mask_valid = False
        ok = False
        error = f"{type(exc).__name__}: {exc}"

    return {
        "ok": ok,
        "backend": backend,
        "canonical_backend": canonical,
        "engine": "photoholmes_upstream",
        "photoholmes_available": True,
        "photoholmes_detail": import_detail,
        "method": method_name or None,
        "sample_score": round(float(score), 6) if score is not None else None,
        "mask_valid": mask_valid,
        "latency_ms": round((time.time() - started) * 1000.0, 2),
        "error": error,
    }


def _init_once(backend: str) -> Dict[str, Any]:
    global ACTIVE_BACKEND
    global ACTIVE_CANONICAL
    global ACTIVE_METHOD
    global ACTIVE_PREPROCESS
    global INIT_PAYLOAD

    backend = _normalize_backend(backend)
    ACTIVE_BACKEND = backend
    ACTIVE_CANONICAL = _canonical_backend(backend)
    probe_payload = _run_probe(backend)
    if probe_payload.get("ok"):
        _canonical, method, preprocess = _load_method(backend)
        ACTIVE_METHOD = method
        ACTIVE_PREPROCESS = preprocess
    else:
        ACTIVE_METHOD = None
        ACTIVE_PREPROCESS = None
    INIT_PAYLOAD = probe_payload
    return INIT_PAYLOAD


@APP.get("/health")
def health():
    payload = dict(INIT_PAYLOAD)
    payload.update(
        {
            "model_name": MODEL_NAMES.get(ACTIVE_BACKEND, "PhotoHolmesCPU"),
            "backend": ACTIVE_BACKEND,
            "canonical_backend": ACTIVE_CANONICAL,
            "weights_root": str(MODELS_ROOT),
        }
    )
    return jsonify(payload), (200 if payload.get("ok") else 500)


@APP.post("/predict/image")
def predict_image():
    started = time.time()
    payload = request.get_json(silent=True) or {}
    image_path = payload.get("image_path")
    request_id = _sanitize_request_id(payload.get("request_id"))
    source_type = payload.get("source_type") or "image"

    if not image_path:
        return jsonify({"ok": False, "error": "image_path is required"}), 400
    if not INIT_PAYLOAD.get("ok"):
        return jsonify({"ok": False, "error": INIT_PAYLOAD.get("error") or "backend not initialized"}), 503

    try:
        image = _load_image(str(image_path))
        forged_score, mask_norm = _analyze_image(image)
        label = "Forged" if forged_score >= 0.5 else "Authentic"
        mask_path = _save_mask(mask_norm, ACTIVE_BACKEND, request_id)
        latency_ms = round((time.time() - started) * 1000.0, 2)
        return jsonify(
            {
                "ok": True,
                "request_id": request_id,
                "source_type": source_type,
                "backend": ACTIVE_BACKEND,
                "canonical_backend": ACTIVE_CANONICAL,
                "model_name": MODEL_NAMES.get(ACTIVE_BACKEND, "PhotoHolmesCPU"),
                "forged_score": round(float(forged_score), 6),
                "label": label,
                "mask_path": mask_path,
                "latency_ms": latency_ms,
                "error": None,
            }
        )
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "request_id": request_id,
                "source_type": source_type,
                "backend": ACTIVE_BACKEND,
                "canonical_backend": ACTIVE_CANONICAL,
                "model_name": MODEL_NAMES.get(ACTIVE_BACKEND, "PhotoHolmesCPU"),
                "forged_score": None,
                "label": None,
                "mask_path": None,
                "latency_ms": round((time.time() - started) * 1000.0, 2),
                "error": f"{type(exc).__name__}: {exc}",
            }
        ), 500


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PhotoHolmes hidden detector sidecar.")
    parser.add_argument(
        "--backend",
        choices=SUPPORTED_BACKENDS,
        default=os.environ.get("T07_PHOTOHOLMES_BACKEND", "noiseprint"),
    )
    parser.add_argument("--probe", action="store_true", help="Run backend probe and exit.")
    parser.add_argument("--host", default="", help="Override host.")
    parser.add_argument("--port", type=int, default=0, help="Override port.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backend = _normalize_backend(args.backend)
    init_payload = _init_once(backend)
    if args.probe:
        print(json.dumps(init_payload, ensure_ascii=True))
        return 0 if init_payload.get("ok") else 1

    host, port = _resolve_host_port(backend)
    if args.host:
        host = args.host
    if args.port > 0:
        port = int(args.port)
    APP.run(host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
