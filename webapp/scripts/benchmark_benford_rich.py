from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

WEBAPP_ROOT = Path(__file__).resolve().parents[1]
if str(WEBAPP_ROOT) not in sys.path:
    sys.path.insert(0, str(WEBAPP_ROOT))

from website.ImageForgeryDetection.FakeImageDetector import FID


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark current vs BenfordRich vs fused detectors.")
    parser.add_argument(
        "--sample-set",
        action="append",
        dest="sample_sets",
        required=True,
        help="Path to a sample set directory containing manifest.csv",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("benchmarks") / "benford_rich"),
        help="Directory for benchmark outputs.",
    )
    return parser.parse_args()


def to_binary_label(value: str) -> int:
    normalized = str(value).strip().lower()
    if normalized in {"authentic", "0", "real", "original"}:
        return 0
    if normalized in {"forged", "1", "fake", "tampered"}:
        return 1
    raise ValueError(f"Unsupported label value: {value}")


def label_text_to_binary(label: str) -> int:
    normalized = str(label).strip().lower()
    if normalized == "authentic":
        return 0
    if normalized == "forged":
        return 1
    if normalized == "review":
        raise ValueError("Review should not be converted directly; use final_score instead.")
    raise ValueError(f"Unsupported prediction label: {label}")


def metrics_from_scores(y_true, scores):
    y_pred = [1 if float(score) >= 0.5 else 0 for score in scores]
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_forged": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall_forged": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1_forged": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc_forged": float(roc_auc_score(y_true, scores)),
        "confusion_matrix_labels_0auth_1forged": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
        "prediction_unique_labels": sorted(set(y_pred)),
    }


def evaluate_sample_set(sample_dir: Path, output_root: Path) -> dict:
    manifest_path = sample_dir / "manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.csv missing: {manifest_path}")

    df = pd.read_csv(manifest_path)
    path_column = "local_path"
    label_column = "label"
    if path_column not in df.columns or label_column not in df.columns:
        raise ValueError(f"manifest missing required columns in {manifest_path}")

    fid = FID()
    prediction_rows = []
    y_true = []
    scores = {
        "current_cnn_only": [],
        "current_hybrid": [],
        "benford_rich_only": [],
        "benford_rich_mun_fused": [],
    }

    for row in df.to_dict(orient="records"):
        image_path = Path(row[path_column])
        if not image_path.exists():
            raise FileNotFoundError(f"sample image missing: {image_path}")
        y = to_binary_label(row[label_column])
        y_true.append(y)

        cnn = fid.predict_cnn_only_structured(str(image_path))
        legacy = fid.predict_legacy_current_structured(str(image_path))
        benford = fid.predict_benford_rich_structured(str(image_path), source_type="image")
        fused = fid.predict_result_structured(str(image_path), source_type="image", require_hidden=True)

        scores["current_cnn_only"].append(float(cnn["score_forged"]))
        scores["current_hybrid"].append(float(legacy["score_forged"]))
        scores["benford_rich_only"].append(float(benford["score_forged"]))
        scores["benford_rich_mun_fused"].append(float(fused["final_score_forged"]))

        prediction_rows.append(
            {
                "local_path": str(image_path),
                "true_label": y,
                "current_cnn_score_forged": float(cnn["score_forged"]),
                "current_cnn_label": cnn["label"],
                "current_hybrid_score_forged": float(legacy["score_forged"]),
                "current_hybrid_label": legacy["label"],
                "benford_rich_score_forged": float(benford["score_forged"]),
                "benford_rich_label": benford["label"],
                "fused_score_forged": float(fused["final_score_forged"]),
                "fused_label": fused["final_label"],
                "fused_requires_review": bool(fused["requires_review"]),
            }
        )

    metrics = {name: metrics_from_scores(y_true, value) for name, value in scores.items()}

    compare_rows = []
    for model_name, model_metrics in metrics.items():
        compare_rows.append(
            {
                "model": model_name,
                "accuracy": model_metrics["accuracy"],
                "f1_forged": model_metrics["f1_forged"],
                "precision_forged": model_metrics["precision_forged"],
                "recall_forged": model_metrics["recall_forged"],
                "roc_auc_forged": model_metrics["roc_auc_forged"],
            }
        )

    output_root.mkdir(parents=True, exist_ok=True)
    slug = sample_dir.name
    pd.DataFrame(prediction_rows).to_csv(output_root / f"{slug}_predictions.csv", index=False)
    pd.DataFrame(compare_rows).to_csv(output_root / f"{slug}_compare.csv", index=False)
    with (output_root / f"{slug}_metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)

    return {
        "sample_set": slug,
        "metrics": metrics,
    }


def build_gate_report(results: list[dict]) -> dict:
    by_name = {item["sample_set"]: item["metrics"] for item in results}
    same_domain = by_name.get("casia_same_domain_100")
    external = by_name.get("external_hf_splicing_mix_100")

    gate = {
        "same_domain_ok": None,
        "external_ok": None,
        "pass": False,
    }
    if same_domain:
        gate["same_domain_ok"] = (
            same_domain["benford_rich_only"]["accuracy"] >= same_domain["current_hybrid"]["accuracy"] - 0.02
        )
    if external:
        external_acc_gain = external["benford_rich_only"]["accuracy"] - external["current_hybrid"]["accuracy"]
        external_f1_gain = external["benford_rich_only"]["f1_forged"] - external["current_hybrid"]["f1_forged"]
        gate["external_ok"] = (external_acc_gain >= 0.05) or (external_f1_gain >= 0.05)
        gate["external_accuracy_gain"] = external_acc_gain
        gate["external_f1_gain"] = external_f1_gain
    gate["pass"] = bool(gate["same_domain_ok"] and gate["external_ok"])
    return gate


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_dir)
    results = []
    for sample_set in args.sample_sets:
        results.append(evaluate_sample_set(Path(sample_set), output_root))
    gate = build_gate_report(results)
    with (output_root / "gate_report.json").open("w", encoding="utf-8") as handle:
        json.dump({"results": results, "gate": gate}, handle, indent=2)
    print(json.dumps({"results": results, "gate": gate}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
