from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO_ROOT / "webapp"
SOURCE_MANIFEST = REPO_ROOT / "sample_sets" / "casia_same_domain_100" / "manifest.csv"
DEMO_ROOT = REPO_ROOT / "sample_sets" / "demo_pack"
SELECTED_ROOT = DEMO_ROOT / "selected_good_cases"
PDF_ROOT = DEMO_ROOT / "pdf"
RUNBOOK_PATH = REPO_ROOT / "docs" / "DEMO_RUNBOOK.md"
TOP_K_PER_CLASS = 10


def ensure_dirs() -> None:
    paths = [
        DEMO_ROOT,
        SELECTED_ROOT / "authentic",
        SELECTED_ROOT / "forged",
        PDF_ROOT,
        RUNBOOK_PATH.parent,
    ]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    for folder in [SELECTED_ROOT / "authentic", SELECTED_ROOT / "forged", PDF_ROOT]:
        for item in folder.iterdir():
            if item.is_file():
                item.unlink()


def load_source_rows() -> list[dict]:
    with SOURCE_MANIFEST.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def evaluate_rows(rows: list[dict]) -> list[dict]:
    os.chdir(WEBAPP_ROOT)
    sys.path.insert(0, str(WEBAPP_ROOT))

    from website.ImageForgeryDetection.FakeImageDetector import FID
    from website.ImageForgeryDetection.benford_analysis import (
        HYBRID_FEATURE_ORDER,
        extract_benford_features,
    )

    fid = FID()
    manifest = fid._get_preferred_artifact_manifest()
    cnn_model = fid._load_cnn_model(manifest)
    svm, scaler, metadata = fid._load_hybrid_components(manifest)

    evaluated: list[dict] = []
    for row in rows:
        image_path = row["local_path"]
        x = fid.prepare_image(image_path).reshape(-1, 128, 128, 3)
        y = cnn_model.predict(x, verbose=0)
        p_authentic = float(y[0][0])
        p_forged = 1.0 - p_authentic
        cnn_pred = "authentic" if p_authentic > 0.5 else "forged"

        benford_feats = extract_benford_features(image_path)
        combined = np.hstack(([p_forged], benford_feats)).reshape(1, -1)
        if combined.shape[1] != len(HYBRID_FEATURE_ORDER):
            raise RuntimeError(f"Hybrid feature width mismatch: {combined.shape[1]}")

        hybrid_p_forged = float(svm.predict_proba(scaler.transform(combined))[0][1])
        hybrid_pred = "forged" if hybrid_p_forged > 0.5 else "authentic"
        confidence = hybrid_p_forged if hybrid_pred == "forged" else (1.0 - hybrid_p_forged)

        evaluated.append(
            {
                **row,
                "active_release": manifest["release_id"],
                "feature_schema_version": metadata["feature_schema_version"],
                "cnn_p_authentic": p_authentic,
                "cnn_p_forged": p_forged,
                "cnn_pred_label": cnn_pred,
                "hybrid_p_forged": hybrid_p_forged,
                "hybrid_pred_label": hybrid_pred,
                "hybrid_confidence": confidence,
                "hybrid_correct": int(hybrid_pred == row["label"]),
            }
        )
    return evaluated


def validate_demo_case(image_path: Path, expected_label: str) -> tuple[bool, str, str]:
    sys.path.insert(0, str(WEBAPP_ROOT))
    from website.ImageForgeryDetection.FakeImageDetector import FID

    fid = FID()
    prediction, confidence = fid.predict_result(str(image_path))
    ok = prediction.lower() == expected_label.lower()
    return ok, prediction, confidence


def copy_selected_cases(evaluated: list[dict]) -> list[dict]:
    selected: list[dict] = []
    for label in ("authentic", "forged"):
        subset = [
            row for row in evaluated
            if row["label"] == label and row["hybrid_correct"] == 1
        ]
        subset.sort(key=lambda row: row["hybrid_confidence"], reverse=True)
        idx = 0
        for row in subset:
            if idx >= TOP_K_PER_CLASS:
                break
            src = Path(row["local_path"])
            dst = SELECTED_ROOT / label / f"{label}_{idx + 1:02d}.jpg"
            with Image.open(src) as img:
                img.convert("RGB").save(dst, format="JPEG", quality=95)
            ok, prediction, confidence = validate_demo_case(dst, label)
            if not ok:
                dst.unlink(missing_ok=True)
                continue
            idx += 1
            selected.append(
                {
                    **row,
                    "demo_local_path": str(dst),
                    "demo_filename": dst.name,
                    "expected_label": label,
                    "demo_pred_label": prediction.lower(),
                    "demo_confidence_percent": confidence,
                }
            )
        if idx < TOP_K_PER_CLASS:
            raise RuntimeError(f"Not enough JPG-stable correct {label} cases to build demo pack")
    return selected


def write_demo_manifest(selected: list[dict]) -> Path:
    manifest_path = DEMO_ROOT / "demo_manifest.csv"
    fieldnames = [
        "expected_label",
        "demo_filename",
        "demo_local_path",
        "local_path",
        "zip_member",
        "cnn_pred_label",
        "cnn_p_authentic",
        "cnn_p_forged",
        "hybrid_pred_label",
        "hybrid_p_forged",
        "hybrid_confidence",
        "active_release",
        "feature_schema_version",
        "demo_pred_label",
        "demo_confidence_percent",
    ]
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in selected:
            writer.writerow({key: row.get(key) for key in fieldnames})
    return manifest_path


def create_pdf(pdf_path: Path, image_paths: list[Path], title: str) -> None:
    page_w, page_h = A4
    margin = 36
    doc = canvas.Canvas(str(pdf_path), pagesize=A4)
    for image_path in image_paths:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img_w, img_h = img.size
            scale = min((page_w - 2 * margin) / img_w, (page_h - 2 * margin - 24) / img_h)
            draw_w = img_w * scale
            draw_h = img_h * scale
            x = (page_w - draw_w) / 2
            y = (page_h - draw_h) / 2 - 12
            doc.setFont("Helvetica-Bold", 12)
            doc.drawString(margin, page_h - margin + 6, title)
            doc.drawImage(ImageReader(img), x, y, width=draw_w, height=draw_h)
            doc.showPage()
    doc.save()


def write_metadata(selected: list[dict], manifest_path: Path) -> None:
    metadata = {
        "source_manifest": str(SOURCE_MANIFEST),
        "demo_manifest": str(manifest_path),
        "selected_per_class": TOP_K_PER_CLASS,
        "class_counts": {"authentic": TOP_K_PER_CLASS, "forged": TOP_K_PER_CLASS},
        "active_release": selected[0]["active_release"],
        "feature_schema_version": selected[0]["feature_schema_version"],
    }
    (DEMO_ROOT / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def write_demo_readme(selected: list[dict]) -> None:
    authentic_names = [row["demo_filename"] for row in selected if row["expected_label"] == "authentic"]
    forged_names = [row["demo_filename"] for row in selected if row["expected_label"] == "forged"]
    text = f"""# Demo Pack

- Source set: `sample_sets/casia_same_domain_100`
- Selection rule: high-confidence same-domain cases that remain correct after normalization to `.jpg`
- Active release used for selection: `{selected[0]["active_release"]}`
- Demo images are normalized to `.jpg` for a safer live upload flow.

## Structure

- `selected_good_cases/authentic/`
- `selected_good_cases/forged/`
- `pdf/demo_authentic_pages.pdf`
- `pdf/demo_forged_pages.pdf`
- `demo_manifest.csv`

## Notes

- These files are preselected to make the live image/PDF demo stable.
- Use the prepared `.jpg` files first in the live flow. PNG should be shown only as a secondary example.
- Do not use this pack as a benchmark; it is a curated demo set.

## Authentic Cases

{chr(10).join(f"- `{name}`" for name in authentic_names)}

## Forged Cases

{chr(10).join(f"- `{name}`" for name in forged_names)}
"""
    (DEMO_ROOT / "README.md").write_text(text, encoding="utf-8")


def write_runbook(selected: list[dict]) -> None:
    authentic = [row["demo_filename"] for row in selected if row["expected_label"] == "authentic"]
    forged = [row["demo_filename"] for row in selected if row["expected_label"] == "forged"]
    text = f"""# Demo Runbook

## Scope

- Live demo target: `image + pdf`
- Runtime: active release `run_20260306_055001`
- Demo assets: `sample_sets/demo_pack`

## Pre-demo Checklist

1. `git pull`
2. `cd webapp`
3. `install.bat`
4. `status.bat`
5. `start.bat`
6. `python scripts/preflight_demo_assets.py`

## What To Demo

1. Upload 2 authentic JPEGs from `sample_sets/demo_pack/selected_good_cases/authentic/`
2. Upload 2 forged JPEGs from `sample_sets/demo_pack/selected_good_cases/forged/`
3. Upload `sample_sets/demo_pack/pdf/demo_authentic_pages.pdf`
4. Upload `sample_sets/demo_pack/pdf/demo_forged_pages.pdf`

## Recommended Order

### Authentic

{chr(10).join(f"- `{name}`" for name in authentic[:4])}

### Forged

{chr(10).join(f"- `{name}`" for name in forged[:4])}

## Talking Points

1. The system is optimized for classical image tampering and JPEG-centric forensic analysis.
2. PDF pages are converted to images and analyzed page by page.
3. Confidence and localization outputs help explain the prediction.
4. For the best live result, use prepared JPEG examples instead of random web images.

## Guardrails

1. Do not lead with external random images.
2. Do not claim universal deepfake detection.
3. Use PNG only as a secondary example.
4. If a live random image looks uncertain, switch back to the prepared demo pack.
"""
    RUNBOOK_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    rows = load_source_rows()
    evaluated = evaluate_rows(rows)
    selected = copy_selected_cases(evaluated)
    manifest_path = write_demo_manifest(selected)
    write_metadata(selected, manifest_path)
    write_demo_readme(selected)

    authentic_pdf_images = [
        Path(row["demo_local_path"]) for row in selected if row["expected_label"] == "authentic"
    ][:3]
    forged_pdf_images = [
        Path(row["demo_local_path"]) for row in selected if row["expected_label"] == "forged"
    ][:3]
    create_pdf(PDF_ROOT / "demo_authentic_pages.pdf", authentic_pdf_images, "Authentic Demo PDF")
    create_pdf(PDF_ROOT / "demo_forged_pages.pdf", forged_pdf_images, "Forged Demo PDF")
    write_runbook(selected)
    print(f"Demo pack written to {DEMO_ROOT}")
    print(f"Runbook written to {RUNBOOK_PATH}")


if __name__ == "__main__":
    main()
