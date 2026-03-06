from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import joblib
import h5py
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_ROOT = PROJECT_ROOT / "models"
RELEASES_ROOT = MODELS_ROOT / "releases"
ARCHIVE_ROOT = MODELS_ROOT / "archive"
ACTIVE_RELEASE_PATH = MODELS_ROOT / "active_release.json"
BENFORD_MODULE_PATH = (
    PROJECT_ROOT / "website" / "ImageForgeryDetection" / "benford_analysis.py"
)

LEGACY_RUNTIME_FILES = [
    "proposed_ela_50_casia_fidac.h5",
    "hybrid_svm_model.pkl",
    "hybrid_scaler.pkl",
    "hybrid_metadata.json",
]
REQUIRED_RELEASE_FILES = [
    "hybrid_svm_model.pkl",
    "hybrid_scaler.pkl",
    "hybrid_metadata.json",
    "run_summary.json",
    "hybrid_holdout_metrics.json",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Activate an image release bundle into webapp/models."
    )
    parser.add_argument(
        "--zip",
        dest="zip_path",
        default=str(MODELS_ROOT / "run_20260306_055001_artifacts.zip"),
        help="Path to the release zip artifact.",
    )
    parser.add_argument(
        "--release-id",
        default="run_20260306_055001",
        help="Release id used under models/releases/<release-id>.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing release directory if it already exists.",
    )
    return parser.parse_args()


def load_benford_module():
    spec = importlib.util.spec_from_file_location(
        "release_benford_contract", BENFORD_MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def prepare_pickle_compat():
    import sys

    sys.modules.setdefault("numpy._core", np.core)
    sys.modules.setdefault("numpy._core.multiarray", np.core.multiarray)


def relative_to_models(path: Path) -> str:
    return path.relative_to(MODELS_ROOT).as_posix()


def snapshot_copy(source: Path, destination_root: Path):
    if not source.exists() or not source.is_file():
        return None
    relative = source.relative_to(MODELS_ROOT)
    destination = destination_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return relative.as_posix()


def snapshot_current_runtime(release_id: str):
    snapshot_dir = ARCHIVE_ROOT / f"active_before_{release_id}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    snapshot_info = {
        "release_id_before_activation": None,
        "snapshot_created_at": datetime.now(timezone.utc).isoformat(),
        "copied_files": [],
    }

    if ACTIVE_RELEASE_PATH.exists():
        active_manifest = json.loads(ACTIVE_RELEASE_PATH.read_text(encoding="utf-8"))
        snapshot_info["release_id_before_activation"] = active_manifest.get(
            "release_id", "unknown"
        )
        copied = snapshot_copy(ACTIVE_RELEASE_PATH, snapshot_dir)
        if copied:
            snapshot_info["copied_files"].append(copied)

        for key in [
            "cnn_model_path",
            "svm_model_path",
            "scaler_path",
            "metadata_path",
            "metrics_path",
            "run_summary_path",
        ]:
            value = active_manifest.get(key)
            if not value:
                continue
            source = Path(value)
            if not source.is_absolute():
                source = MODELS_ROOT / value
            copied = snapshot_copy(source, snapshot_dir)
            if copied:
                snapshot_info["copied_files"].append(copied)
    else:
        snapshot_info["release_id_before_activation"] = "legacy_canonical"
        for name in LEGACY_RUNTIME_FILES:
            copied = snapshot_copy(MODELS_ROOT / name, snapshot_dir)
            if copied:
                snapshot_info["copied_files"].append(copied)

    (snapshot_dir / "snapshot_info.json").write_text(
        json.dumps(snapshot_info, indent=2),
        encoding="utf-8",
    )
    return snapshot_dir


def extract_release(zip_path: Path, release_dir: Path, force: bool):
    if release_dir.exists():
        if not force:
            raise FileExistsError(
                f"Release directory already exists: {release_dir}. Use --force to replace it."
            )
        shutil.rmtree(release_dir)

    release_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(release_dir)


def select_cnn_model_path(release_dir: Path) -> Path:
    candidates = sorted(
        path for path in release_dir.glob("*.h5") if path.name != "segmenter_weights.h5"
    )
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected exactly one CNN .h5 in {release_dir}, found {len(candidates)}"
        )
    return candidates[0]


def normalize_keras_config_value(value):
    if isinstance(value, dict):
        if value.get("class_name") == "DTypePolicy":
            return value.get("config", {}).get("name", "float32")

        normalized = {
            key: normalize_keras_config_value(sub_value)
            for key, sub_value in value.items()
        }
        if normalized.get("class_name") == "InputLayer":
            config = normalized.get("config", {})
            if (
                isinstance(config, dict)
                and "batch_shape" in config
                and "batch_input_shape" not in config
            ):
                config["batch_input_shape"] = config.pop("batch_shape")
        return normalized

    if isinstance(value, list):
        return [normalize_keras_config_value(item) for item in value]

    return value


def build_runtime_compatible_cnn_copy(release_dir: Path, cnn_model_path: Path) -> Path:
    compat_name = f"runtime_compat_{cnn_model_path.name}"
    compat_path = release_dir / compat_name
    shutil.copy2(cnn_model_path, compat_path)

    with h5py.File(compat_path, "r+") as h5_file:
        model_config = h5_file.attrs.get("model_config")
        if model_config is None:
            raise ValueError(f"model_config missing in H5 file: {cnn_model_path}")

        model_config_text = (
            model_config.decode("utf-8")
            if isinstance(model_config, bytes)
            else model_config
        )
        normalized_config = normalize_keras_config_value(json.loads(model_config_text))
        h5_file.attrs.modify(
            "model_config",
            json.dumps(normalized_config).encode("utf-8"),
        )

    return compat_path


def build_runtime_metadata(release_dir: Path, release_id: str, contract_module):
    raw_metadata_path = release_dir / "hybrid_metadata.json"
    holdout_metrics_path = release_dir / "hybrid_holdout_metrics.json"

    raw_metadata = json.loads(raw_metadata_path.read_text(encoding="utf-8"))
    holdout_metrics = json.loads(holdout_metrics_path.read_text(encoding="utf-8"))
    cnn_model_path = select_cnn_model_path(release_dir)
    runtime_cnn_model_path = build_runtime_compatible_cnn_copy(release_dir, cnn_model_path)

    contract = contract_module.get_feature_contract()
    compatible_versions = set(
        contract_module.get_compatible_feature_schema_versions()
    )
    metadata_version = raw_metadata.get(
        "feature_schema_version", contract["feature_schema_version"]
    )
    if metadata_version not in compatible_versions:
        raise ValueError(
            "Unsupported feature_schema_version in artifact: "
            f"{metadata_version} not in {sorted(compatible_versions)}"
        )

    prepare_pickle_compat()
    scaler = joblib.load(release_dir / "hybrid_scaler.pkl")
    feature_count = getattr(scaler, "n_features_in_", None)
    expected_feature_count = len(contract["hybrid_feature_order"])
    if feature_count != expected_feature_count:
        raise ValueError(
            f"Scaler feature count mismatch: got={feature_count} expected={expected_feature_count}"
        )

    runtime_metadata = dict(raw_metadata)
    runtime_metadata["feature_schema_version"] = metadata_version
    runtime_metadata["label_mapping"] = contract["label_mapping"]
    runtime_metadata["cnn_score_semantics"] = contract["cnn_score_semantics"]
    runtime_metadata["benford_chi_scale"] = contract["benford_chi_scale"]
    runtime_metadata["benford_feature_order"] = contract["benford_feature_order"]
    runtime_metadata["hybrid_feature_order"] = contract["hybrid_feature_order"]
    runtime_metadata["selected_cnn_model_path"] = (
        f"releases/{release_id}/{runtime_cnn_model_path.name}"
    )
    runtime_metadata["metrics_hybrid_holdout"] = raw_metadata.get(
        "metrics_hybrid_holdout", holdout_metrics
    )

    runtime_metadata_path = release_dir / "runtime_hybrid_metadata.json"
    runtime_metadata_path.write_text(
        json.dumps(runtime_metadata, indent=2),
        encoding="utf-8",
    )
    return runtime_cnn_model_path, runtime_metadata_path


def validate_release_files(release_dir: Path):
    missing = [name for name in REQUIRED_RELEASE_FILES if not (release_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Release missing required files: {missing}")


def write_active_release(release_id: str, release_dir: Path, cnn_model_path: Path, metadata_path: Path):
    active_manifest = {
        "release_id": release_id,
        "cnn_model_path": relative_to_models(cnn_model_path),
        "svm_model_path": relative_to_models(release_dir / "hybrid_svm_model.pkl"),
        "scaler_path": relative_to_models(release_dir / "hybrid_scaler.pkl"),
        "metadata_path": relative_to_models(metadata_path),
        "metrics_path": relative_to_models(release_dir / "hybrid_holdout_metrics.json"),
        "run_summary_path": relative_to_models(release_dir / "run_summary.json"),
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }
    ACTIVE_RELEASE_PATH.write_text(
        json.dumps(active_manifest, indent=2),
        encoding="utf-8",
    )
    return active_manifest


def main():
    args = parse_args()
    zip_path = Path(args.zip_path).resolve()
    release_id = args.release_id

    if not zip_path.exists():
        raise FileNotFoundError(f"Artifact zip not found: {zip_path}")

    contract_module = load_benford_module()
    release_dir = RELEASES_ROOT / release_id

    snapshot_dir = snapshot_current_runtime(release_id)
    extract_release(zip_path, release_dir, force=args.force)
    validate_release_files(release_dir)
    cnn_model_path, metadata_path = build_runtime_metadata(
        release_dir, release_id, contract_module
    )
    active_manifest = write_active_release(
        release_id, release_dir, cnn_model_path, metadata_path
    )

    print("Activated release:", release_id)
    print("Snapshot directory:", snapshot_dir)
    print("Release directory:", release_dir)
    print("CNN model:", cnn_model_path.name)
    print("Metadata:", metadata_path.name)
    print("Active manifest:", ACTIVE_RELEASE_PATH)
    print(json.dumps(active_manifest, indent=2))


if __name__ == "__main__":
    main()
