from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


WEBAPP_ROOT = Path(__file__).resolve().parents[1]
HIDDEN_ROOT = WEBAPP_ROOT / "hidden_detectors" / "photoholmes"
MANIFEST_PATH = HIDDEN_ROOT / "model_manifest.json"
VENV_ROOT = WEBAPP_ROOT / ".venv-photoholmes311"
PYTHON_BIN = VENV_ROOT / "Scripts" / "python.exe"
REQUIREMENTS_PATH = HIDDEN_ROOT / "requirements.txt"
SERVER_PATH = HIDDEN_ROOT / "server.py"
SUPPORTED_BACKENDS = ("noiseprint", "comprint")
DEFAULT_BACKEND = "noiseprint"
PHOTOHOLMES_GIT_URL = "git+https://github.com/photoholmes/photoholmes.git"


def _normalize_backend(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in SUPPORTED_BACKENDS:
        return raw
    if raw == "all":
        return "all"
    env_backend = str(os.environ.get("T07_HIDDEN_BACKEND", "")).strip().lower()
    if env_backend in SUPPORTED_BACKENDS:
        return env_backend
    return DEFAULT_BACKEND


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage PhotoHolmes hidden detector runtime.")
    parser.add_argument("mode", choices=["install", "status", "start", "stop", "probe"])
    parser.add_argument(
        "--backend",
        default=os.environ.get("T07_HIDDEN_BACKEND", DEFAULT_BACKEND),
        help="noiseprint | comprint | all (all only for install/status)",
    )
    return parser.parse_args()


def _resolve_backends(mode: str, backend_arg: str) -> list[str]:
    backend = _normalize_backend(backend_arg)
    if backend == "all":
        if mode not in {"install", "status"}:
            raise ValueError("--backend all is only valid for install/status")
        return list(SUPPORTED_BACKENDS)
    return [backend]


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _parse_backend_url(backend: str, default_host: str, default_port: int) -> tuple[str, int]:
    env_name = f"T07_HIDDEN_DETECTOR_URL_{backend.upper()}"
    raw = str(os.environ.get(env_name, "")).strip()
    if not raw:
        return default_host, default_port
    parsed = urlparse(raw)
    if parsed.scheme and parsed.hostname and parsed.port:
        return parsed.hostname, int(parsed.port)
    return default_host, default_port


def _host_port_for_backend(backend: str) -> tuple[str, int]:
    manifest = _load_manifest()
    cfg = (manifest.get("sidecars", {}) or {}).get(backend, {})
    default_host = str(cfg.get("host", "127.0.0.1"))
    default_port = int(cfg.get("port", 8013 if backend == "noiseprint" else 8014))
    return _parse_backend_url(backend, default_host, default_port)


def _health_url(backend: str) -> str:
    host, port = _host_port_for_backend(backend)
    return f"http://{host}:{port}/health"


def ensure_venv() -> None:
    if PYTHON_BIN.exists():
        return
    if os.name == "nt":
        try:
            subprocess.run(["py", "-3.11", "-m", "venv", str(VENV_ROOT)], check=True)
            return
        except Exception:
            pass
    subprocess.run([sys.executable, "-m", "venv", str(VENV_ROOT)], check=True)


def ensure_python_compatible() -> None:
    result = subprocess.run(
        [str(PYTHON_BIN), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    version_text = (result.stdout or "").strip()
    parts = version_text.split(".")
    major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    if (major, minor) < (3, 10):
        raise RuntimeError(
            "PhotoHolmes runtime requires Python >= 3.10. "
            f"Detected {version_text} at {PYTHON_BIN}."
        )


def pip_install(args: list[str]) -> None:
    subprocess.run([str(PYTHON_BIN), "-m", "pip", *args], check=True)


def is_photoholmes_ready() -> bool:
    if not PYTHON_BIN.exists():
        return False
    probe_code = (
        "import photoholmes; "
        "from photoholmes.methods.splicebuster import Splicebuster; "
        "from photoholmes.methods.noisesniffer import Noisesniffer; "
        "print('ok')"
    )
    result = subprocess.run(
        [str(PYTHON_BIN), "-c", probe_code],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    return result.returncode == 0


def check_health(backend: str, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(_health_url(backend), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok"):
            detail = payload.get("engine") or payload.get("model_name") or "ok"
            return True, str(detail)
        return False, str(payload.get("error") or "health check failed")
    except Exception as exc:
        return False, str(exc)


def _run_probe_subprocess(backend: str, timeout: float = 120.0) -> tuple[bool, str]:
    if not PYTHON_BIN.exists():
        return False, f"venv missing: {PYTHON_BIN}"
    try:
        ensure_python_compatible()
    except Exception as exc:
        return False, str(exc)
    try:
        result = subprocess.run(
            [str(PYTHON_BIN), str(SERVER_PATH), "--backend", backend, "--probe"],
            cwd=str(WEBAPP_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"probe timed out after {timeout:.0f}s"
    except Exception as exc:
        return False, f"probe execution failed: {exc}"

    output = (result.stdout or "").strip()
    error_text = (result.stderr or "").strip()
    if result.returncode == 0:
        return True, output or "probe passed"
    detail = output or error_text or f"probe exit code={result.returncode}"
    return False, detail


def running_pid_for_port(port: int) -> int | None:
    try:
        output = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
        )
    except Exception:
        return None
    needle = f":{port}"
    for line in output.splitlines():
        if needle in line and "LISTENING" in line:
            parts = line.split()
            if parts:
                try:
                    return int(parts[-1])
                except ValueError:
                    return None
    return None


def running_pids_for_port_windows(port: int) -> list[int]:
    if os.name != "nt":
        return []
    script = (
        f"Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty OwningProcess"
    )
    try:
        output = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
        )
    except Exception:
        return []
    pids: list[int] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.append(int(line))
        except ValueError:
            continue
    return sorted(set(pids))


def _log_path(backend: str) -> Path:
    return WEBAPP_ROOT / f"hidden_detector_{backend}.log"


def install_runtime(backends: list[str]) -> int:
    ensure_venv()
    ensure_python_compatible()
    pip_install(["install", "--upgrade", "pip"])
    pip_install(["install", "-r", str(REQUIREMENTS_PATH)])
    pip_install(["install", "torch==2.5.1", "--index-url", "https://download.pytorch.org/whl/cpu"])
    if not is_photoholmes_ready():
        # Install upstream PhotoHolmes package without its full dependency set
        # (jpegio and other heavy extras are not required for our selected CPU methods).
        pip_install(["install", "--upgrade", PHOTOHOLMES_GIT_URL, "--no-deps"])
    else:
        print("[INFO] PhotoHolmes package already available; skip reinstall.")

    exit_code = 0
    for backend in backends:
        ok, detail = _run_probe_subprocess(backend)
        if ok:
            print(f"[INFO] PhotoHolmes probe passed for backend={backend}")
        else:
            print(f"[WARNING] PhotoHolmes probe failed for backend={backend}: {detail}")
            exit_code = 1
    return exit_code


def print_status(backends: list[str]) -> int:
    overall_ok = True
    print("[PhotoHolmes Detector]")
    print(f"  venv: {'OK' if PYTHON_BIN.exists() else 'MISSING'} - {PYTHON_BIN}")
    for backend in backends:
        host, port = _host_port_for_backend(backend)
        port_pid = running_pid_for_port(port)
        extra_pids = running_pids_for_port_windows(port)
        all_pids = sorted(set(([port_pid] if port_pid else []) + extra_pids))
        health_ok, health_detail = check_health(backend, timeout=2.0)
        probe_ok, probe_detail = _run_probe_subprocess(backend, timeout=60.0)

        print(f"  backend[{backend}]:")
        print(f"    url: http://{host}:{port}")
        print(f"    port_state: {'RUNNING' if all_pids else 'STOPPED'}")
        if all_pids:
            print(f"    pid: {', '.join(str(item) for item in all_pids)}")
        print(f"    health: {'OK' if health_ok else 'FAILED'} - {health_detail}")
        print(f"    probe: {'PASS' if probe_ok else 'FAILED'}")
        if not probe_ok:
            print(f"    probe_detail: {probe_detail}")

        overall_ok = overall_ok and health_ok and probe_ok
    return 0 if overall_ok else 1


def start_runtime(backend: str) -> int:
    if not PYTHON_BIN.exists():
        print(f"[ERROR] PhotoHolmes venv missing: {PYTHON_BIN}")
        return 1

    probe_ok, probe_detail = _run_probe_subprocess(backend)
    if not probe_ok:
        print(f"[ERROR] PhotoHolmes probe failed for backend={backend}: {probe_detail}")
        return 1

    ok, detail = check_health(backend, timeout=2.0)
    if ok:
        print(f"PhotoHolmes backend '{backend}' already running ({detail})")
        return 0

    host, port = _host_port_for_backend(backend)
    log_path = _log_path(backend)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("a", encoding="utf-8")

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    env = dict(os.environ)
    env["T07_PHOTOHOLMES_BACKEND"] = backend
    subprocess.Popen(
        [str(PYTHON_BIN), str(SERVER_PATH), "--backend", backend, "--host", host, "--port", str(port)],
        cwd=str(WEBAPP_ROOT),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=creationflags,
        close_fds=False,
    )

    for _ in range(45):
        time.sleep(1)
        healthy, health_detail = check_health(backend, timeout=2.0)
        if healthy:
            print(f"PhotoHolmes backend '{backend}' started successfully ({health_detail})")
            return 0

    print(f"[ERROR] PhotoHolmes backend '{backend}' failed to start within timeout.")
    return 1


def stop_runtime(backend: str) -> int:
    _host, port = _host_port_for_backend(backend)
    pid_candidates = []
    pid = running_pid_for_port(port)
    if pid:
        pid_candidates.append(pid)
    pid_candidates.extend(running_pids_for_port_windows(port))
    pid_candidates = sorted(set(pid_candidates))

    if not pid_candidates:
        print(f"PhotoHolmes backend '{backend}' already stopped on port {port}")
        return 0

    for candidate in pid_candidates:
        subprocess.run(["taskkill", "/PID", str(candidate), "/F"], check=False)
    time.sleep(1)
    print(f"PhotoHolmes backend '{backend}' stopped (pid={', '.join(str(p) for p in pid_candidates)})")
    return 0


def run_probe_mode(backend: str) -> int:
    ok, detail = _run_probe_subprocess(backend)
    print("[PhotoHolmes Probe]")
    print(f"  backend: {backend}")
    print(f"  result: {'PASS' if ok else 'FAIL'}")
    if detail:
        print(f"  detail: {detail}")
    return 0 if ok else 1


def main() -> int:
    args = parse_args()
    backends = _resolve_backends(args.mode, args.backend)

    if args.mode == "install":
        return install_runtime(backends)
    if args.mode == "status":
        return print_status(backends)
    if args.mode == "start":
        return start_runtime(backends[0])
    if args.mode == "stop":
        return stop_runtime(backends[0])
    if args.mode == "probe":
        return run_probe_mode(backends[0])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
