from __future__ import annotations

import ast
import json
import os
import re
import time
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, request


APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parents[1]
VENDOR_ROOT = APP_ROOT / "upstream_vendor"
VENDOR_MMSEG_ROOT = VENDOR_ROOT / "mmseg"
MODELS_ROOT = PROJECT_ROOT / "models" / "hidden_detectors" / "mun"
WEIGHTS_ROOT = MODELS_ROOT / "weights"
OUTPUT_ROOT = MODELS_ROOT / "outputs"
MANIFEST_PATH = APP_ROOT / "model_manifest.json"
CONFIG_PATH = APP_ROOT / "mun_conf.py"

app = Flask(__name__)
MODEL = None
MODEL_NAME = "MUN"
DEVICE = "cpu"

if str(VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(VENDOR_ROOT))


FORCED_VENDOR_MODULE_FILES = {
    "mmseg.datasets.transforms.transforms": VENDOR_MMSEG_ROOT / "datasets" / "transforms" / "transforms.py",
    "mmseg.datasets.transforms.formatting": VENDOR_MMSEG_ROOT / "datasets" / "transforms" / "formatting.py",
    "mmseg.models.segmentors.npp": VENDOR_MMSEG_ROOT / "models" / "segmentors" / "npp.py",
    "mmseg.models.decode_heads.nu_head": VENDOR_MMSEG_ROOT / "models" / "decode_heads" / "nu_head.py",
    "mmseg.models.losses.iou_loss": VENDOR_MMSEG_ROOT / "models" / "losses" / "iou_loss.py",
}
OPTIONAL_IMPORT_MODULES: list[str] = []
CACHE_PURGE_PREFIXES = tuple(
    sorted(
        {
            *FORCED_VENDOR_MODULE_FILES.keys(),
            *OPTIONAL_IMPORT_MODULES,
            "mmseg.datasets.transforms.NoisePrintPlus",
        }
    )
)
REQUIRED_TRANSFORMS = (
    "NPPTest",
    "NPPResize",
    "NPPResizeToMultiple",
    "NPPPackSegInputs",
)
REQUIRED_VENDOR_CLASSES = {
    "mmseg.datasets.transforms.transforms": (
        "NPPTest",
        "NPPResize",
        "NPPResizeToMultiple",
    ),
    "mmseg.datasets.transforms.formatting": ("NPPPackSegInputs",),
}
VENDOR_PACKAGE_PATHS = {
    "mmseg.datasets": VENDOR_MMSEG_ROOT / "datasets",
    "mmseg.models": VENDOR_MMSEG_ROOT / "models",
    "mmseg.datasets.transforms": VENDOR_MMSEG_ROOT / "datasets" / "transforms",
    "mmseg.models.segmentors": VENDOR_MMSEG_ROOT / "models" / "segmentors",
    "mmseg.models.decode_heads": VENDOR_MMSEG_ROOT / "models" / "decode_heads",
    "mmseg.models.losses": VENDOR_MMSEG_ROOT / "models" / "losses",
}


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


def _prepend_vendor_subpackage_paths() -> None:
    for package_name, vendor_path in VENDOR_PACKAGE_PATHS.items():
        package = importlib.import_module(package_name)
        current_paths = list(getattr(package, "__path__", []))
        vendor_path_str = str(vendor_path.resolve())
        if vendor_path_str not in current_paths:
            package.__path__ = [vendor_path_str, *current_paths]


def _is_within_vendor(file_path: str) -> bool:
    try:
        resolved = Path(file_path).resolve()
    except Exception:
        return False
    resolved_norm = os.path.normcase(str(resolved))
    vendor_norm = os.path.normcase(str(VENDOR_ROOT.resolve()))
    return resolved_norm == vendor_norm or resolved_norm.startswith(vendor_norm + os.sep)


def _purge_custom_modules() -> None:
    for name in list(sys.modules.keys()):
        for prefix in CACHE_PURGE_PREFIXES:
            if name == prefix or name.startswith(prefix + "."):
                sys.modules.pop(name, None)
                break


def _force_load_module_from_file(module_name: str, module_path: Path):
    module_path = module_path.resolve()
    if not module_path.exists():
        raise FileNotFoundError(f"Required vendor module missing: {module_path}")

    parent_name, _, child_name = module_name.rpartition(".")
    if parent_name:
        parent_module = importlib.import_module(parent_name)
    else:
        parent_module = None

    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to build import spec for {module_name} from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    if parent_module is not None:
        setattr(parent_module, child_name, module)
    spec.loader.exec_module(module)
    return module


def _collect_registered_classes_by_registry(module_path: Path) -> Dict[str, list[str]]:
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    registered: Dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for deco in node.decorator_list:
            if not isinstance(deco, ast.Call):
                continue
            func = deco.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.attr == "register_module"
            ):
                registered.setdefault(func.value.id, []).append(node.name)
                break
    return registered


def _ensure_custom_registrations(strict: bool = True) -> Dict[str, Any]:
    importlib.invalidate_caches()
    _prepend_vendor_subpackage_paths()
    _purge_custom_modules()

    # Make registration deterministic across repeated probe/start calls.
    import mmseg.registry as mmseg_registry
    from mmengine.registry import Registry
    from mmseg.registry import TRANSFORMS

    for name in REQUIRED_TRANSFORMS:
        TRANSFORMS.module_dict.pop(name, None)

    loaded_from: Dict[str, str] = {}
    module_issues: list[str] = []

    original_register_module = Registry.register_module

    def _register_module_force(self, name=None, force=False, module=None):  # type: ignore[override]
        return original_register_module(self, name=name, force=True, module=module)

    Registry.register_module = _register_module_force  # type: ignore[assignment]
    try:
        for module_name, module_file in FORCED_VENDOR_MODULE_FILES.items():
            registered = _collect_registered_classes_by_registry(module_file)
            for registry_name, class_names in registered.items():
                registry_obj = getattr(mmseg_registry, registry_name, None)
                module_dict = getattr(registry_obj, "module_dict", None)
                if module_dict is None:
                    continue
                for class_name in class_names:
                    module_dict.pop(class_name, None)
            module = _force_load_module_from_file(module_name, module_file)
            loaded_from[module_name] = str(Path(getattr(module, "__file__", "<unknown>")).resolve())
    finally:
        Registry.register_module = original_register_module  # type: ignore[assignment]

    for module_name in OPTIONAL_IMPORT_MODULES:
        module = importlib.import_module(module_name)
        loaded_from[module_name] = str(Path(getattr(module, "__file__", "<unknown>")).resolve())

    for module_name in FORCED_VENDOR_MODULE_FILES:
        loaded_path = loaded_from.get(module_name, "")
        if not _is_within_vendor(loaded_path):
            module_issues.append(f"{module_name} loaded from non-vendor path: {loaded_path}")

    for module_name, required_classes in REQUIRED_VENDOR_CLASSES.items():
        module = sys.modules.get(module_name)
        if module is None:
            module_issues.append(f"{module_name} not found in sys.modules")
            continue
        for class_name in required_classes:
            if not hasattr(module, class_name):
                module_issues.append(f"{module_name} missing class {class_name}")

    missing = [name for name in REQUIRED_TRANSFORMS if name not in TRANSFORMS.module_dict]
    mmseg_module_path = str(Path(importlib.import_module("mmseg").__file__).resolve())
    result: Dict[str, Any] = {
        "ok": not missing and not module_issues,
        "required_transforms": list(REQUIRED_TRANSFORMS),
        "missing_transforms": missing,
        "module_issues": module_issues,
        "mmseg_module_path": mmseg_module_path,
        "custom_module_sources": loaded_from,
    }

    if strict and not result["ok"]:
        details = []
        if missing:
            details.append("missing transforms: " + ", ".join(missing))
        if module_issues:
            details.append("module issues: " + "; ".join(module_issues))
        raise RuntimeError(
            "MUN custom registration validation failed. "
            + " | ".join(details)
            + ". Loaded mmseg from "
            + mmseg_module_path
            + ". Loaded custom module sources: "
            + json.dumps(loaded_from, ensure_ascii=True)
        )
    return result


def probe_custom_registrations() -> Dict[str, Any]:
    return _ensure_custom_registrations(strict=False)


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

    _ensure_custom_registrations()
    from mmseg.apis import inference_model, init_model  # noqa: F401

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
    print("Preloading MUN model...", flush=True)
    load_model_once()
    print(f"MUN model ready on device={DEVICE}", flush=True)
    app.run(host=host, port=port)
