from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

WEBAPP_ROOT = Path(__file__).resolve().parents[1]
if str(WEBAPP_ROOT) not in sys.path:
    sys.path.insert(0, str(WEBAPP_ROOT))

from website.ImageForgeryDetection.FakeImageDetector import FID
from website.ImageForgeryDetection.fusion import build_current_only_result, fuse_detector_votes
from website.ImageForgeryDetection.hidden_detector_client import (
    check_hidden_detector_health,
    create_request_id,
    predict_hidden_detector,
)


DEFAULT_BACKENDS = ["noiseprint", "comprint"]
MANAGE_BACKEND_SCRIPT = WEBAPP_ROOT / "scripts" / "manage_hidden_backend.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark CNN-only against CNN + hidden backends with accuracy and latency gates."
    )
    parser.add_argument(
        "--sample-set",
        action="append",
        dest="sample_sets",
        required=True,
        help="Path to sample set directory containing manifest.csv",
    )
    parser.add_argument(
        "--backend",
        action="append",
        dest="backends",
        default=[],
        help="Hidden backend name. Repeat for multiple values.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("benchmarks") / "hidden_backends"),
        help="Directory for benchmark outputs.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Per-request timeout for hidden backend sidecars (seconds).",
    )
    parser.add_argument(
        "--gate-path",
        default=str(WEBAPP_ROOT / "models" / "hidden_backend_gate.json"),
        help="Where to write gate decision json.",
    )
    parser.add_argument(
        "--write-gate",
        action="store_true",
        help="Write gate result json for runtime selection.",
    )
    parser.add_argument(
        "--target-backend",
        default="",
        help="Optional preferred backend if it passes all gates.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip backend probe/health validation before benchmark.",
    )
    return parser.parse_args()


def to_binary_label(value: str) -> int:
    normalized = str(value).strip().lower()
    if normalized in {"authentic", "0", "real", "original"}:
        return 0
    if normalized in {"forged", "1", "fake", "tampered"}:
        return 1
    raise ValueError(f"Unsupported label value: {value}")


def metrics_from_scores(y_true: list[int], scores: list[float]) -> dict:
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


def latency_stats(latencies_ms: list[float]) -> dict:
    if not latencies_ms:
        return {
            "count": 0,
            "avg": None,
            "min": None,
            "max": None,
            "p95": None,
        }

    values = np.array(latencies_ms, dtype=float)
    return {
        "count": int(values.size),
        "avg": float(values.mean()),
        "min": float(values.min()),
        "max": float(values.max()),
        "p95": float(np.percentile(values, 95)),
    }


def run_backend_preflight(backends: list[str], timeout: float) -> None:
    for backend in backends:
        if backend == "off":
            continue

        probe = subprocess.run(
            [sys.executable, str(MANAGE_BACKEND_SCRIPT), "probe", "--backend", backend],
            cwd=str(WEBAPP_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        if probe.returncode != 0:
            output = (probe.stdout or "").strip()
            error = (probe.stderr or "").strip()
            detail = output or error or f"probe exit={probe.returncode}"
            raise RuntimeError(f"Preflight probe failed for backend={backend}: {detail}")

        health_payload = check_hidden_detector_health(timeout=min(max(timeout, 2.0), 10.0), backend=backend)
        if not isinstance(health_payload, dict) or not health_payload.get("ok"):
            raise RuntimeError(
                f"Preflight health check failed for backend={backend}: "
                f"{health_payload if health_payload else 'no payload'}"
            )


def evaluate_sample_set(sample_dir: Path, backends: list[str], timeout: float, output_root: Path) -> dict:
    manifest_path = sample_dir / "manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.csv missing: {manifest_path}")

    df = pd.read_csv(manifest_path)
    if "local_path" not in df.columns or "label" not in df.columns:
        raise ValueError(f"manifest missing required columns in {manifest_path}")

    fid = FID()
    y_true: list[int] = []
    cnn_scores: list[float] = []
    fused_scores: dict[str, list[float]] = {backend: [] for backend in backends}
    backend_latencies: dict[str, list[float]] = {backend: [] for backend in backends}
    backend_failures: dict[str, int] = {backend: 0 for backend in backends}
    rows: list[dict] = []

    for row in df.to_dict(orient="records"):
        image_path = Path(row["local_path"])
        if not image_path.exists():
            raise FileNotFoundError(f"sample image missing: {image_path}")

        y = to_binary_label(row["label"])
        y_true.append(y)

        cnn = fid.predict_cnn_only_structured(str(image_path))
        cnn_score = float(cnn["score_forged"])
        cnn_scores.append(cnn_score)

        prediction_row: dict[str, object] = {
            "local_path": str(image_path),
            "true_label": y,
            "cnn_score_forged": cnn_score,
            "cnn_label": cnn["label"],
            "cnn_pred_label": 1 if cnn_score >= 0.5 else 0,
        }

        for backend in backends:
            start = time.time()
            hidden_error = ""
            try:
                hidden = predict_hidden_detector(
                    str(image_path),
                    source_type="image",
                    request_id=create_request_id(),
                    timeout=timeout,
                    backend=backend,
                    enforce_gate=False,
                )
                fused = fuse_detector_votes(
                    cnn_score,
                    cnn["source"],
                    float(hidden["forged_score"]),
                    str(hidden["label"]),
                    hidden_mask_path=hidden.get("mask_path"),
                    hidden_model_name=hidden.get("model_name"),
                    hidden_latency_ms=hidden.get("latency_ms"),
                    hidden_backend=backend,
                )
                latency_ms = float(hidden.get("latency_ms") or ((time.time() - start) * 1000.0))
                backend_latencies[backend].append(latency_ms)
                prediction_row[f"{backend}_hidden_ok"] = 1
                prediction_row[f"{backend}_hidden_latency_ms"] = round(latency_ms, 2)
            except Exception as exc:
                backend_failures[backend] += 1
                hidden_error = f"{type(exc).__name__}: {exc}"
                fused = build_current_only_result(cnn_score, cnn["source"], hidden_backend=backend)
                prediction_row[f"{backend}_hidden_ok"] = 0
                prediction_row[f"{backend}_hidden_latency_ms"] = None

            fused_score = float(fused["final_score_forged"])
            fused_scores[backend].append(fused_score)
            prediction_row[f"{backend}_fused_score_forged"] = fused_score
            prediction_row[f"{backend}_fused_label"] = fused["final_label"]
            prediction_row[f"{backend}_fused_pred_label"] = 1 if fused_score >= 0.5 else 0
            prediction_row[f"{backend}_decision_mode"] = fused["decision_mode"]
            prediction_row[f"{backend}_hidden_error"] = hidden_error

        rows.append(prediction_row)

    metrics = {
        "cnn_only": metrics_from_scores(y_true, cnn_scores),
        "hidden_fused": {
            backend: metrics_from_scores(y_true, fused_scores[backend]) for backend in backends
        },
        "hidden_latency_ms": {
            backend: latency_stats(backend_latencies[backend]) for backend in backends
        },
        "hidden_failures": {
            backend: {
                "count": int(backend_failures[backend]),
                "ratio": float(backend_failures[backend] / max(len(rows), 1)),
            }
            for backend in backends
        },
        "sample_size_total": len(rows),
        "class_counts": {
            "authentic": int(sum(1 for item in y_true if item == 0)),
            "forged": int(sum(1 for item in y_true if item == 1)),
        },
    }

    compare_rows = [
        {
            "model": "cnn_only",
            **{k: metrics["cnn_only"][k] for k in ["accuracy", "f1_forged", "precision_forged", "recall_forged", "roc_auc_forged"]},
            "latency_avg_ms": None,
            "latency_p95_ms": None,
            "hidden_failure_ratio": 0.0,
        }
    ]

    for backend in backends:
        fused_metric = metrics["hidden_fused"][backend]
        latency_metric = metrics["hidden_latency_ms"][backend]
        compare_rows.append(
            {
                "model": f"cnn_plus_{backend}",
                **{k: fused_metric[k] for k in ["accuracy", "f1_forged", "precision_forged", "recall_forged", "roc_auc_forged"]},
                "latency_avg_ms": latency_metric["avg"],
                "latency_p95_ms": latency_metric["p95"],
                "hidden_failure_ratio": metrics["hidden_failures"][backend]["ratio"],
            }
        )

    output_root.mkdir(parents=True, exist_ok=True)
    slug = sample_dir.name
    pd.DataFrame(rows).to_csv(output_root / f"{slug}_predictions.csv", index=False)
    pd.DataFrame(compare_rows).to_csv(output_root / f"{slug}_compare.csv", index=False)
    with (output_root / f"{slug}_metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)

    # Rows where backend corrected a CNN-only mistake.
    for backend in backends:
        fixed_rows = []
        for item in rows:
            true_label = int(item["true_label"])
            cnn_pred = int(item["cnn_pred_label"])
            backend_pred = int(item.get(f"{backend}_fused_pred_label", cnn_pred))
            hidden_ok = int(item.get(f"{backend}_hidden_ok", 0))
            if cnn_pred != true_label and backend_pred == true_label:
                fixed_rows.append(
                    {
                        "local_path": item["local_path"],
                        "true_label": true_label,
                        "cnn_pred_label": cnn_pred,
                        "backend_pred_label": backend_pred,
                        "cnn_score_forged": item["cnn_score_forged"],
                        "backend_score_forged": item.get(f"{backend}_fused_score_forged"),
                        "hidden_ok": hidden_ok,
                        "decision_mode": item.get(f"{backend}_decision_mode"),
                    }
                )
        pd.DataFrame(fixed_rows).to_csv(output_root / f"{slug}_fixed_vs_cnn_{backend}.csv", index=False)

    return {
        "sample_set": slug,
        "metrics": metrics,
    }


def build_gate_report(results: list[dict], backends: list[str]) -> dict:
    by_name = {item["sample_set"]: item["metrics"] for item in results}
    same_domain = by_name.get("casia_same_domain_100")
    external = by_name.get("external_hf_splicing_mix_100")

    gate_by_backend = {}
    for backend in backends:
        same_domain_ok = None
        external_ok = None
        latency_ok = None
        external_accuracy_gain = None
        external_f1_gain = None
        same_domain_accuracy_drop = None
        latency_avg = None
        latency_p95 = None

        if same_domain:
            cnn_same_acc = same_domain["cnn_only"]["accuracy"]
            backend_same_acc = same_domain["hidden_fused"][backend]["accuracy"]
            same_domain_accuracy_drop = cnn_same_acc - backend_same_acc
            same_domain_ok = same_domain_accuracy_drop <= 0.02

        if external:
            cnn_external_acc = external["cnn_only"]["accuracy"]
            backend_external_acc = external["hidden_fused"][backend]["accuracy"]
            cnn_external_f1 = external["cnn_only"]["f1_forged"]
            backend_external_f1 = external["hidden_fused"][backend]["f1_forged"]
            external_accuracy_gain = backend_external_acc - cnn_external_acc
            external_f1_gain = backend_external_f1 - cnn_external_f1
            external_ok = (external_accuracy_gain >= 0.03) or (external_f1_gain >= 0.05)

            latency_stats_external = external["hidden_latency_ms"][backend]
            latency_avg = latency_stats_external["avg"]
            latency_p95 = latency_stats_external["p95"]

        if latency_avg is not None and latency_p95 is not None:
            latency_ok = latency_avg <= 5000.0 and latency_p95 <= 8000.0

        checks = [same_domain_ok, external_ok, latency_ok]
        pass_gate = all(item is True for item in checks)
        reasons = []
        if same_domain_ok is False:
            reasons.append(
                f"same-domain drop={same_domain_accuracy_drop:.4f} (>0.02)"
            )
        if external_ok is False:
            reasons.append(
                f"external gains too low (acc={external_accuracy_gain:.4f}, f1={external_f1_gain:.4f})"
            )
        if latency_ok is False:
            reasons.append(
                f"latency too high (avg={latency_avg:.2f}ms, p95={latency_p95:.2f}ms)"
            )
        if not reasons:
            reasons.append("All gates passed")

        gate_by_backend[backend] = {
            "pass": pass_gate,
            "same_domain_ok": same_domain_ok,
            "external_ok": external_ok,
            "latency_ok": latency_ok,
            "same_domain_accuracy_drop": same_domain_accuracy_drop,
            "external_accuracy_gain": external_accuracy_gain,
            "external_f1_gain": external_f1_gain,
            "latency_avg_ms": latency_avg,
            "latency_p95_ms": latency_p95,
            "reason": "; ".join(reasons),
        }

    return {
        "backends": gate_by_backend,
        "has_same_domain_set": same_domain is not None,
        "has_external_set": external is not None,
    }


def choose_selected_backend(gate_report: dict, preferred: str) -> str:
    gates = gate_report.get("backends", {})
    preferred_key = str(preferred or "").strip().lower()
    if preferred_key and preferred_key in gates and gates[preferred_key].get("pass"):
        return preferred_key

    passing = [
        (name, payload)
        for name, payload in gates.items()
        if payload.get("pass")
    ]
    if not passing:
        return "off"

    passing.sort(
        key=lambda item: (
            item[1].get("external_f1_gain") or -999.0,
            item[1].get("external_accuracy_gain") or -999.0,
        ),
        reverse=True,
    )
    return passing[0][0]


def write_gate_file(gate_path: Path, selected_backend: str, gate_report: dict) -> None:
    selected_payload = gate_report["backends"].get(selected_backend, {})
    final_pass = bool(selected_payload.get("pass")) if selected_backend != "off" else False

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "selected_backend": selected_backend,
        "gate": {
            "pass": final_pass,
            "reason": selected_payload.get("reason") if selected_backend != "off" else "No backend passed all gates",
        },
        "backends": gate_report["backends"],
    }
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    backends = [item.strip().lower() for item in args.backends if item.strip()]
    if not backends:
        backends = list(DEFAULT_BACKENDS)

    if not args.skip_preflight:
        run_backend_preflight(backends, timeout=float(args.timeout))

    output_root = Path(args.output_dir)
    results = []
    for sample in args.sample_sets:
        results.append(
            evaluate_sample_set(
                sample_dir=Path(sample),
                backends=backends,
                timeout=float(args.timeout),
                output_root=output_root,
            )
        )

    gate_report = build_gate_report(results, backends)
    selected_backend = choose_selected_backend(gate_report, args.target_backend)

    summary = {
        "results": results,
        "gate": gate_report,
        "selected_backend": selected_backend,
    }

    with (output_root / "gate_report.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    if args.write_gate:
        write_gate_file(Path(args.gate_path), selected_backend, gate_report)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
