from __future__ import annotations

from typing import Any, Dict


LABEL_AUTHENTIC = "Authentic"
LABEL_FORGED = "Forged"
LABEL_REVIEW = "Review"

CURRENT_WEIGHT = 0.4
HIDDEN_WEIGHT = 0.6


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def label_from_score(score: float, threshold: float = 0.5) -> str:
    return LABEL_FORGED if clamp_score(score) >= threshold else LABEL_AUTHENTIC


def leaning_from_score(score: float) -> tuple[str, float]:
    normalized = clamp_score(score)
    leaning_label = label_from_score(normalized)
    leaning_confidence = (
        normalized if leaning_label == LABEL_FORGED else (1.0 - normalized)
    ) * 100.0
    return leaning_label, round(leaning_confidence, 2)


def build_current_only_result(
    score_forged: float,
    source: str,
    hidden_backend: str | None = None,
) -> Dict[str, Any]:
    score = clamp_score(score_forged)
    label = label_from_score(score)
    leaning_label, leaning_confidence = leaning_from_score(score)
    return {
        "current_score_forged": score,
        "current_label": label,
        "current_confidence": leaning_confidence,
        "current_source": source,
        "hidden_backend": hidden_backend,
        "hidden_score_forged": None,
        "hidden_label": None,
        "hidden_confidence": None,
        "hidden_mask_path": None,
        "hidden_model_name": None,
        "hidden_latency_ms": None,
        "hidden_available": False,
        "final_score_forged": score,
        "final_label": label,
        "final_confidence": leaning_confidence,
        "leaning_label": leaning_label,
        "leaning_confidence": leaning_confidence,
        "requires_review": False,
        "decision_mode": "current_only",
    }


def fuse_detector_votes(
    current_score_forged: float,
    current_source: str,
    hidden_score_forged: float,
    hidden_label: str,
    hidden_mask_path: str | None = None,
    hidden_model_name: str | None = None,
    hidden_latency_ms: float | None = None,
    hidden_backend: str | None = None,
) -> Dict[str, Any]:
    current_score = clamp_score(current_score_forged)
    hidden_score = clamp_score(hidden_score_forged)
    final_score = clamp_score((CURRENT_WEIGHT * current_score) + (HIDDEN_WEIGHT * hidden_score))
    leaning_label, leaning_confidence = leaning_from_score(final_score)

    if current_score < 0.40 and hidden_score < 0.40:
        final_label = LABEL_AUTHENTIC
    elif current_score >= 0.65 and hidden_score >= 0.65:
        final_label = LABEL_FORGED
    elif hidden_score >= 0.85 and current_score >= 0.45:
        final_label = LABEL_FORGED
    elif current_score >= 0.85 and hidden_score >= 0.45:
        final_label = LABEL_FORGED
    else:
        final_label = LABEL_REVIEW

    if final_label == LABEL_AUTHENTIC:
        final_confidence = (1.0 - final_score) * 100.0
    elif final_label == LABEL_FORGED:
        final_confidence = final_score * 100.0
    else:
        final_confidence = leaning_confidence
    requires_review = final_label == LABEL_REVIEW

    return {
        "current_score_forged": round(current_score, 6),
        "current_label": label_from_score(current_score),
        "current_confidence": round(
            (current_score if current_score >= 0.5 else (1.0 - current_score)) * 100.0,
            2,
        ),
        "current_source": current_source,
        "hidden_backend": hidden_backend,
        "hidden_score_forged": round(hidden_score, 6),
        "hidden_label": hidden_label or label_from_score(hidden_score),
        "hidden_confidence": round(
            (hidden_score if hidden_score >= 0.5 else (1.0 - hidden_score)) * 100.0,
            2,
        ),
        "hidden_mask_path": hidden_mask_path,
        "hidden_model_name": hidden_model_name,
        "hidden_latency_ms": hidden_latency_ms,
        "hidden_available": True,
        "final_score_forged": round(final_score, 6),
        "final_label": final_label,
        "final_confidence": round(final_confidence, 2),
        "leaning_label": leaning_label,
        "leaning_confidence": leaning_confidence,
        "requires_review": requires_review,
        "decision_mode": "fused_hidden_mun",
    }
