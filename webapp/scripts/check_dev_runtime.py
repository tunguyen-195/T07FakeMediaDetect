from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_ROOT = PROJECT_ROOT / "models"
ACTIVE_RELEASE_PATH = MODELS_ROOT / "active_release.json"
SEGMENTER_PATH = MODELS_ROOT / "segmenter_weights.h5"
VIDEO_MODEL_PATH = MODELS_ROOT / "forgery_model_me.hdf5"

REQUIRED_MANIFEST_KEYS = [
    "release_id",
    "cnn_model_path",
    "svm_model_path",
    "scaler_path",
    "metadata_path",
    "metrics_path",
    "run_summary_path",
    "activated_at",
]

REQUIRED_METADATA_KEYS = [
    "feature_schema_version",
    "label_mapping",
    "cnn_score_semantics",
    "hybrid_feature_order",
    "benford_feature_order",
    "benford_chi_scale",
    "selected_cnn_model_path",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the local dev runtime bundle.")
    parser.add_argument(
        "--mode",
        choices=["install", "start", "status"],
        default="status",
        help="Output style and exit behavior.",
    )
    return parser.parse_args()


def resolve_models_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return MODELS_ROOT / candidate


def find_poppler_path() -> Path | None:
    env_value = os.environ.get("POPPLER_PATH")
    if env_value:
        env_path = Path(env_value)
        if env_path.is_file() and env_path.name.lower() == "pdfinfo.exe":
            return env_path.parent
        if env_path.is_dir() and (env_path / "pdfinfo.exe").exists():
            return env_path

    pdfinfo_exe = shutil.which("pdfinfo")
    if pdfinfo_exe:
        return Path(pdfinfo_exe).parent

    project_poppler = PROJECT_ROOT / "poppler" / "Library" / "bin"
    if (project_poppler / "pdfinfo.exe").exists():
        return project_poppler

    candidates = [
        Path(r"C:\ProgramData\chocolatey\lib\poppler\tools"),
        Path.home() / "scoop" / "apps" / "poppler" / "current" / "bin",
        Path(r"C:\Program Files\poppler\bin"),
        Path(r"C:\Program Files (x86)\poppler\bin"),
        Path(r"C:\poppler\Library\bin"),
        Path(r"C:\poppler\bin"),
    ]
    for candidate in candidates:
        if (candidate / "pdfinfo.exe").exists():
            return candidate
    return None


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_active_release() -> dict:
    issues: list[str] = []
    warnings: list[str] = []
    details: dict[str, str] = {}

    if not ACTIVE_RELEASE_PATH.exists():
        issues.append("active_release.json missing")
        return {"ok": False, "issues": issues, "warnings": warnings, "details": details}

    try:
        manifest = load_json(ACTIVE_RELEASE_PATH)
    except Exception as exc:
        issues.append(f"active_release.json unreadable: {exc}")
        return {"ok": False, "issues": issues, "warnings": warnings, "details": details}

    missing_keys = [key for key in REQUIRED_MANIFEST_KEYS if not manifest.get(key)]
    if missing_keys:
        issues.append(f"active_release.json missing keys: {missing_keys}")
        return {"ok": False, "issues": issues, "warnings": warnings, "details": details}

    details["release_id"] = manifest["release_id"]
    details["activated_at"] = manifest["activated_at"]

    resolved_paths = {}
    for key in REQUIRED_MANIFEST_KEYS:
        if key in {"release_id", "activated_at"}:
            continue
        resolved = resolve_models_path(manifest[key])
        resolved_paths[key] = resolved
        if resolved is None or not resolved.exists():
            issues.append(f"{key} missing: {manifest[key]}")

    metadata_path = resolved_paths.get("metadata_path")
    if metadata_path and metadata_path.exists():
        try:
            metadata = load_json(metadata_path)
            metadata_missing = [
                key for key in REQUIRED_METADATA_KEYS if key not in metadata
            ]
            if metadata_missing:
                issues.append(f"runtime_hybrid_metadata.json missing keys: {metadata_missing}")
            else:
                details["feature_schema_version"] = metadata["feature_schema_version"]
                details["cnn_score_semantics"] = metadata["cnn_score_semantics"]
                details["selected_cnn_model_path"] = metadata["selected_cnn_model_path"]
                selected_cnn_path = resolve_models_path(metadata["selected_cnn_model_path"])
                if selected_cnn_path is None or not selected_cnn_path.exists():
                    issues.append(
                        "selected_cnn_model_path missing: "
                        f"{metadata['selected_cnn_model_path']}"
                    )
                elif resolved_paths.get("cnn_model_path") != selected_cnn_path:
                    warnings.append(
                        "active_release cnn_model_path differs from metadata selected_cnn_model_path"
                    )
        except Exception as exc:
            issues.append(f"runtime_hybrid_metadata.json unreadable: {exc}")

    details["cnn_model"] = Path(manifest["cnn_model_path"]).name
    details["svm_model"] = Path(manifest["svm_model_path"]).name
    details["scaler"] = Path(manifest["scaler_path"]).name
    details["metrics"] = Path(manifest["metrics_path"]).name

    return {
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
        "details": details,
    }


def print_check(label: str, ok: bool, detail: str = "") -> None:
    status = "OK" if ok else "MISSING"
    if detail:
        print(f"  {label}: {status} - {detail}")
    else:
        print(f"  {label}: {status}")


def print_runtime_summary(release_result: dict, poppler_path: Path | None) -> None:
    details = release_result["details"]
    print("[Runtime Bundle]")
    print_check("Active release manifest", ACTIVE_RELEASE_PATH.exists(), ACTIVE_RELEASE_PATH.name)
    print_check("Image runtime bundle", release_result["ok"], details.get("release_id", "unknown"))
    if details:
        print(f"  release_id: {details.get('release_id', 'unknown')}")
        print(f"  activated_at: {details.get('activated_at', 'unknown')}")
        print(f"  cnn_model: {details.get('cnn_model', 'unknown')}")
        print(f"  schema: {details.get('feature_schema_version', 'unknown')}")
    for warning in release_result["warnings"]:
        print(f"  WARNING: {warning}")
    for issue in release_result["issues"]:
        print(f"  ERROR: {issue}")

    print("[Supporting Files]")
    print_check("Segmenter weights", SEGMENTER_PATH.exists(), SEGMENTER_PATH.name)
    if poppler_path is not None:
        print_check("Poppler", True, str(poppler_path))
    else:
        print_check("Poppler", False, "run install_poppler.bat")
    print_check("Video model (optional)", VIDEO_MODEL_PATH.exists(), VIDEO_MODEL_PATH.name)


def main() -> int:
    args = parse_args()
    release_result = check_active_release()
    poppler_path = find_poppler_path()

    if args.mode == "status":
        print_runtime_summary(release_result, poppler_path)

    required_ok = release_result["ok"] and SEGMENTER_PATH.exists() and poppler_path is not None
    if args.mode != "status":
        if required_ok:
            print("Runtime bundle validation: OK")
            print(f"Active release: {release_result['details'].get('release_id', 'unknown')}")
        else:
            print("Runtime bundle validation: FAILED")
            print_runtime_summary(release_result, poppler_path)

    return 0 if required_ok else 1


if __name__ == "__main__":
    sys.exit(main())
