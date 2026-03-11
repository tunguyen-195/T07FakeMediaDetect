from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST_PATH = REPO_ROOT / "T07FakeMediaDetect_AI" / "latest_training_datasets.json"
DEFAULT_BUNDLED_KAGGLE_JSON = REPO_ROOT / "T07FakeMediaDetect_AI" / "bootstrap" / "kaggle.json"
DEFAULT_DATA_ROOT = REPO_ROOT / "Datasets"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download the 2 datasets used by the latest training notebook "
            "(Benford_SVM_FullData_Colab.ipynb) and bootstrap Kaggle auth."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help=f"Dataset manifest JSON path (default: {DEFAULT_MANIFEST_PATH})",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help=f"Base directory for downloaded datasets (default: {DEFAULT_DATA_ROOT})",
    )
    parser.add_argument(
        "--kaggle-json",
        type=Path,
        default=DEFAULT_BUNDLED_KAGGLE_JSON,
        help=f"Kaggle API credential JSON to copy before download (default: {DEFAULT_BUNDLED_KAGGLE_JSON})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if the target folder already has enough images.",
    )
    parser.add_argument(
        "--keep-existing-auth",
        action="store_true",
        help="Keep the current %%USERPROFILE%%\\.kaggle\\kaggle.json if it already exists.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Optional path for the JSON report. Defaults to <data-root>/latest_training_download_report.json.",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if "datasets" not in payload or not isinstance(payload["datasets"], list) or not payload["datasets"]:
        raise RuntimeError(f"Manifest is missing a non-empty 'datasets' list: {path}")
    return payload


def ensure_kaggle_cli_installed() -> None:
    if importlib.util.find_spec("kaggle") is not None:
        return
    print("[INFO] Installing Kaggle CLI (kaggle==1.6.17)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "kaggle==1.6.17"])


def ensure_kaggle_auth(source_json: Path, keep_existing_auth: bool) -> Path:
    if not source_json.exists():
        raise FileNotFoundError(f"Kaggle credential JSON not found: {source_json}")

    with source_json.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    missing_keys = sorted({"username", "key"} - set(payload))
    if missing_keys:
        raise RuntimeError(f"Kaggle credential JSON missing keys: {', '.join(missing_keys)}")

    target_dir = Path.home() / ".kaggle"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_json = target_dir / "kaggle.json"

    if target_json.exists() and keep_existing_auth:
        print(f"[INFO] Keeping existing Kaggle auth: {target_json}")
        return target_json

    shutil.copy2(source_json, target_json)
    try:
        os.chmod(target_json, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    print(f"[INFO] Kaggle auth ready at: {target_json}")
    return target_json


def count_images(root: Path) -> int:
    if not root.exists():
        return 0
    total = 0
    for file_path in root.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTS:
            total += 1
    return total


def build_kaggle_api(config_dir: Path):
    os.environ["KAGGLE_CONFIG_DIR"] = str(config_dir)
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    return api


def download_dataset(api, slug: str, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Downloading {slug} -> {target_dir}")
    api.dataset_download_files(slug, path=str(target_dir), unzip=True, force=True, quiet=False)


def resolve_report_path(cli_value: Path | None, data_root: Path) -> Path:
    if cli_value is not None:
        return cli_value
    return data_root / "latest_training_download_report.json"


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    data_root = args.data_root.resolve()
    data_root.mkdir(parents=True, exist_ok=True)

    ensure_kaggle_cli_installed()
    auth_path = ensure_kaggle_auth(args.kaggle_json.resolve(), args.keep_existing_auth)

    kaggle_api = build_kaggle_api(auth_path.parent)

    report_rows = []
    print("[INFO] Source notebook:", manifest.get("generated_from", {}).get("notebook", "unknown"))
    print("[INFO] Data root:", data_root)

    for dataset in manifest["datasets"]:
        name = dataset["name"]
        slug = dataset["slug"]
        target_dir = (data_root / dataset["relative_target_dir"]).resolve()
        min_existing_images = int(dataset.get("min_existing_images", 0))
        before_count = count_images(target_dir)
        status = "skipped"

        if args.force or before_count < min_existing_images:
            download_dataset(kaggle_api, slug, target_dir)
            status = "downloaded"
        else:
            print(
                f"[INFO] Skipping {name}: found {before_count} images in {target_dir} "
                f"(threshold={min_existing_images})"
            )

        after_count = count_images(target_dir)
        if after_count < min_existing_images:
            raise RuntimeError(
                f"{name} download incomplete: expected at least {min_existing_images} images, found {after_count}"
            )

        report_rows.append(
            {
                "name": name,
                "slug": slug,
                "target_dir": str(target_dir),
                "status": status,
                "image_count_before": before_count,
                "image_count_after": after_count,
                "min_existing_images": min_existing_images,
            }
        )
        print(f"[OK] {name}: {after_count} images at {target_dir}")

    report_path = resolve_report_path(args.report_path, data_root).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(args.manifest.resolve()),
        "kaggle_json_source": str(args.kaggle_json.resolve()),
        "kaggle_auth_target": str(auth_path),
        "data_root": str(data_root),
        "datasets": report_rows,
    }
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report_payload, handle, indent=2)

    print()
    print("[DONE] All datasets are ready.")
    print(f"[DONE] Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
