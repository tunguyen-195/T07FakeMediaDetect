from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


WEBAPP_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_MUN = WEBAPP_ROOT / "scripts" / "manage_hidden_detector.py"
SCRIPT_PHOTOHOLMES = WEBAPP_ROOT / "scripts" / "manage_photoholmes_detector.py"
SUPPORTED_BACKENDS = ("off", "noiseprint", "comprint", "mun", "trufor")
DEFAULT_BACKEND = "off"

if str(WEBAPP_ROOT) not in sys.path:
    sys.path.insert(0, str(WEBAPP_ROOT))

from website.ImageForgeryDetection.hidden_detector_client import (  # noqa: E402
    check_hidden_detector_health,
    describe_hidden_backend_state,
    get_hidden_backend_name,
    resolve_hidden_backend_url,
)


def _normalize_backend(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in SUPPORTED_BACKENDS:
        return raw
    env_backend = str(get_hidden_backend_name()).strip().lower()
    if env_backend in SUPPORTED_BACKENDS:
        return env_backend
    return DEFAULT_BACKEND


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch hidden backend management by backend name.")
    parser.add_argument("mode", choices=["install", "status", "start", "stop", "probe"])
    parser.add_argument(
        "--backend",
        default="",
        help="off | noiseprint | comprint | mun | trufor (defaults to T07_HIDDEN_BACKEND or off)",
    )
    return parser.parse_args()


def _run_subprocess(cmd: list[str]) -> int:
    result = subprocess.run(cmd, cwd=str(WEBAPP_ROOT), check=False)
    return int(result.returncode)


def _dispatch_mun(mode: str) -> int:
    return _run_subprocess([sys.executable, str(SCRIPT_MUN), mode])


def _dispatch_photoholmes(mode: str, backend: str) -> int:
    return _run_subprocess([sys.executable, str(SCRIPT_PHOTOHOLMES), mode, "--backend", backend])


def _check_external_backend(backend: str, probe: bool = False) -> int:
    print("[Hidden Backend]")
    print(f"  backend: {backend.upper()}")
    enabled, reason = describe_hidden_backend_state(backend)
    print(f"  gate: {'PASS' if enabled else 'BLOCKED'} - {reason}")

    try:
        url = resolve_hidden_backend_url(backend)
        print(f"  url: {url}")
    except Exception as exc:
        print(f"  url: INVALID - {exc}")
        return 1

    if not enabled:
        print("  health: SKIPPED - backend blocked by gate")
        return 1

    try:
        payload = check_hidden_detector_health(timeout=3.0, backend=backend)
    except Exception as exc:
        print(f"  health: FAILED - {exc}")
        return 1

    ok = bool(payload.get("ok")) if isinstance(payload, dict) else False
    detail = ""
    if isinstance(payload, dict):
        detail = payload.get("device") or payload.get("error") or str(payload)
    print(f"  health: {'OK' if ok else 'FAILED'} - {detail}")

    if probe:
        print(f"  probe: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    args = parse_args()
    backend = _normalize_backend(args.backend)
    mode = args.mode

    if backend == "off":
        print("[Hidden Backend] backend=OFF")
        if mode == "status":
            print("  status: disabled")
        else:
            print(f"  mode={mode}: no-op because backend is disabled")
        return 0

    if backend == "mun":
        return _dispatch_mun(mode)

    if backend in {"noiseprint", "comprint"}:
        return _dispatch_photoholmes(mode, backend)

    # trufor and any future external backends
    if mode in {"status", "probe"}:
        return _check_external_backend(backend, probe=(mode == "probe"))

    print(f"[Hidden Backend] backend={backend.upper()} mode={mode}")
    print("  This backend is externally managed. No local process action performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
