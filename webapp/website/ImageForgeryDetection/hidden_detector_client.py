from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict


SUPPORTED_HIDDEN_BACKENDS = ("off", "mun", "noiseprint", "comprint", "trufor")
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("T07_HIDDEN_DETECTOR_TIMEOUT", "60"))
DEFAULT_BACKEND = os.environ.get("T07_HIDDEN_BACKEND", "off").strip().lower()
DEFAULT_BASE_URLS = {
    "mun": os.environ.get(
        "T07_HIDDEN_DETECTOR_URL_MUN",
        os.environ.get("T07_HIDDEN_DETECTOR_URL", "http://127.0.0.1:8011"),
    ),
    "noiseprint": os.environ.get("T07_HIDDEN_DETECTOR_URL_NOISEPRINT", "http://127.0.0.1:8013"),
    "comprint": os.environ.get("T07_HIDDEN_DETECTOR_URL_COMPRINT", "http://127.0.0.1:8014"),
    "trufor": os.environ.get("T07_HIDDEN_DETECTOR_URL_TRUFOR", "http://127.0.0.1:8015"),
}
DEFAULT_GATE_REQUIRED = os.environ.get("T07_HIDDEN_GATE_REQUIRED", "1").strip() == "1"
DEFAULT_GATE_PATH = Path(
    os.environ.get(
        "T07_HIDDEN_GATE_PATH",
        str(Path(__file__).resolve().parents[2] / "models" / "hidden_backend_gate.json"),
    )
)


def create_request_id() -> str:
    return uuid.uuid4().hex


def _normalize_backend_name(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in SUPPORTED_HIDDEN_BACKENDS:
        return normalized
    return "off"


def get_hidden_backend_name(environ=None) -> str:
    env = environ if environ is not None else os.environ
    return _normalize_backend_name(env.get("T07_HIDDEN_BACKEND", DEFAULT_BACKEND))


def get_hidden_backend_display_name(backend: str | None = None) -> str:
    value = _normalize_backend_name(backend) if backend is not None else get_hidden_backend_name()
    if value == "off":
        return "OFF"
    return value.upper()


def resolve_hidden_backend_url(backend: str | None = None) -> str:
    selected = _normalize_backend_name(backend) if backend is not None else get_hidden_backend_name()
    if selected == "off":
        raise RuntimeError("Hidden backend is disabled (T07_HIDDEN_BACKEND=off).")

    base_url = str(DEFAULT_BASE_URLS.get(selected, "")).strip().rstrip("/")
    if not base_url:
        raise RuntimeError(
            f"Hidden backend '{selected}' has no configured URL. "
            f"Set T07_HIDDEN_DETECTOR_URL_{selected.upper()}."
        )
    return base_url


def _load_gate_payload(gate_path: Path = DEFAULT_GATE_PATH) -> Dict[str, Any]:
    if not gate_path.exists():
        return {}
    try:
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def describe_hidden_backend_state(backend: str | None = None) -> tuple[bool, str]:
    selected = _normalize_backend_name(backend) if backend is not None else get_hidden_backend_name()
    if selected == "off":
        return False, "Hidden backend is disabled (T07_HIDDEN_BACKEND=off)."

    if not DEFAULT_GATE_REQUIRED:
        return True, "Gate check disabled (T07_HIDDEN_GATE_REQUIRED=0)."

    gate_payload = _load_gate_payload()
    if not gate_payload:
        return False, f"Gate file missing or invalid: {DEFAULT_GATE_PATH}"

    selected_backend = _normalize_backend_name(gate_payload.get("selected_backend"))
    global_gate = gate_payload.get("gate", {})
    backend_gate = (gate_payload.get("backends", {}) or {}).get(selected, {})
    backend_pass = bool(backend_gate.get("pass"))
    selected_pass = bool(global_gate.get("pass")) and selected_backend == selected
    if backend_pass or selected_pass:
        return True, "Gate passed."

    reason = str(backend_gate.get("reason") or global_gate.get("reason") or "gate blocked")
    return False, reason


def is_hidden_backend_enabled(backend: str | None = None) -> bool:
    enabled, _reason = describe_hidden_backend_state(backend=backend)
    return enabled


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


def check_hidden_detector_health(timeout: float = 5.0, backend: str | None = None) -> Dict[str, Any]:
    selected = _normalize_backend_name(backend) if backend is not None else get_hidden_backend_name()
    if selected == "off":
        return {
            "ok": False,
            "backend": "off",
            "error": "Hidden backend disabled",
        }

    base_url = resolve_hidden_backend_url(selected)
    with urllib.request.urlopen(f"{base_url}/health", timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, dict):
        payload.setdefault("backend", selected)
    return payload


def predict_hidden_detector(
    image_path: str,
    source_type: str,
    request_id: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    backend: str | None = None,
    enforce_gate: bool = True,
) -> Dict[str, Any]:
    selected = _normalize_backend_name(backend) if backend is not None else get_hidden_backend_name()
    if selected == "off":
        raise RuntimeError("Hidden backend is disabled (T07_HIDDEN_BACKEND=off).")

    if enforce_gate:
        enabled, reason = describe_hidden_backend_state(selected)
        if not enabled:
            raise RuntimeError(f"Hidden backend '{selected}' blocked by gate: {reason}")

    base_url = resolve_hidden_backend_url(selected)
    payload = {
        "image_path": image_path,
        "request_id": request_id or create_request_id(),
        "source_type": source_type,
    }
    try:
        response = _post_json(f"{base_url}/predict/image", payload, timeout=timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Hidden detector HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Hidden detector unavailable: {exc}") from exc

    if not isinstance(response, dict):
        raise RuntimeError("Hidden detector returned non-object JSON")
    if not response.get("ok"):
        raise RuntimeError(response.get("error") or "Hidden detector returned failure")

    required_keys = ["ok", "model_name", "forged_score", "label", "mask_path", "latency_ms"]
    missing = [key for key in required_keys if key not in response]
    if missing:
        raise RuntimeError(f"Hidden detector response missing keys: {missing}")
    response.setdefault("backend", selected)
    return response
