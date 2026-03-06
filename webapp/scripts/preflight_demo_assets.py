from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO_ROOT / "webapp"
DEMO_ROOT = REPO_ROOT / "sample_sets" / "demo_pack"
DEMO_MANIFEST = DEMO_ROOT / "demo_manifest.csv"
PDF_ROOT = DEMO_ROOT / "pdf"
REPORT_PATH = DEMO_ROOT / "preflight_report.json"


def main() -> None:
    if not DEMO_MANIFEST.exists():
        raise FileNotFoundError(f"Demo manifest missing: {DEMO_MANIFEST}")

    os.chdir(WEBAPP_ROOT)
    sys.path.insert(0, str(WEBAPP_ROOT))
    from website.ImageForgeryDetection.FakeImageDetector import FID

    fid = FID()
    runtime_manifest = fid._get_preferred_artifact_manifest()

    rows = list(csv.DictReader(DEMO_MANIFEST.open("r", encoding="utf-8")))
    results = []
    failures = []

    for row in rows:
        prediction, confidence = fid.predict_result(row["demo_local_path"])
        expected = row["expected_label"].capitalize()
        ok = prediction == expected
        result = {
            "file": row["demo_filename"],
            "expected": expected,
            "predicted": prediction,
            "confidence_percent": confidence,
            "ok": ok,
        }
        results.append(result)
        if not ok:
            failures.append(result)

    pdf_checks = []
    for pdf_path in sorted(PDF_ROOT.glob("*.pdf")):
        reader = PdfReader(str(pdf_path))
        pdf_checks.append(
            {
                "file": pdf_path.name,
                "exists": True,
                "pages": len(reader.pages),
            }
        )

    report = {
        "active_release": runtime_manifest["release_id"],
        "demo_manifest": str(DEMO_MANIFEST),
        "image_checks_total": len(results),
        "image_checks_failed": len(failures),
        "image_checks": results,
        "pdf_checks": pdf_checks,
        "overall_ok": len(failures) == 0 and all(item["pages"] > 0 for item in pdf_checks),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
