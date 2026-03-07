from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict

DEFAULT_BASE_URL = os.environ.get("T07_BENFORD_DETECTOR_URL", "http://127.0.0.1:8012")
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("T07_BENFORD_DETECTOR_TIMEOUT", "30"))


def create_request_id() -> str:
    return uuid.uuid4().hex


def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_benford_rich_health(timeout: float = 5.0) -> Dict[str, Any]:
    with urllib.request.urlopen(f"{DEFAULT_BASE_URL}/health", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def predict_benford_rich(
    image_path: str,
    source_type: str,
    request_id: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    payload = {
        "image_path": image_path,
        "request_id": request_id or create_request_id(),
        "source_type": source_type,
    }
    try:
        response = _post_json(f"{DEFAULT_BASE_URL}/predict/image", payload, timeout=timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"BenfordRich detector HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"BenfordRich detector unavailable: {exc}") from exc

    if not isinstance(response, dict):
        raise RuntimeError("BenfordRich detector returned non-object JSON")
    if not response.get("ok"):
        raise RuntimeError(response.get("error") or "BenfordRich detector returned failure")

    required_keys = [
        "ok",
        "model_name",
        "forged_score",
        "label",
        "confidence",
        "latency_ms",
        "feature_width",
        "feature_schema_version",
        "release_id",
    ]
    missing = [key for key in required_keys if key not in response]
    if missing:
        raise RuntimeError(f"BenfordRich detector response missing keys: {missing}")
    return response
