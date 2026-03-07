from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

WEBAPP_ROOT = Path(__file__).resolve().parents[1]
HIDDEN_ROOT = WEBAPP_ROOT / "hidden_detectors" / "benford_rich"
VENV_ROOT = WEBAPP_ROOT / ".venv-benford"
PYTHON_BIN = VENV_ROOT / "Scripts" / "python.exe"
REQUIREMENTS_PATH = HIDDEN_ROOT / "requirements.txt"
SERVER_PATH = HIDDEN_ROOT / "server.py"
MANIFEST_PATH = HIDDEN_ROOT / "model_manifest.json"
ACTIVE_RELEASE_PATH = WEBAPP_ROOT / "models" / "active_benford_release.json"
LOG_PATH = WEBAPP_ROOT / "hidden_detector_benford.log"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage BenfordRich detector runtime.")
    parser.add_argument("mode", choices=["install", "status", "start", "stop"])
    return parser.parse_args()


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def ensure_venv() -> None:
    if PYTHON_BIN.exists():
        return
    subprocess.run([sys.executable, "-m", "venv", str(VENV_ROOT)], check=True)


def pip_install(args: list[str]) -> None:
    subprocess.run([str(PYTHON_BIN), "-m", "pip", *args], check=True)


def health_url() -> str:
    manifest = load_manifest()
    sidecar = manifest["sidecar"]
    return f"http://{sidecar['host']}:{sidecar['port']}/health"


def check_health(timeout: float = 5.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(health_url(), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok"):
            return True, payload.get("release_id", "unknown")
        return False, payload.get("error") or "health check failed"
    except Exception as exc:
        return False, str(exc)


def running_pid_for_port(port: int) -> int | None:
    try:
        output = subprocess.check_output(["netstat", "-ano"], text=True, encoding="utf-8", errors="ignore")
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
        )
    except Exception:
        return []
    pids = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.append(int(line))
        except ValueError:
            continue
    return sorted(set(pids))


def running_server_pids_windows() -> list[int]:
    if os.name != "nt":
        return []
    server_marker = str(SERVER_PATH).replace("\\", "\\\\")
    script = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -like '*{server_marker}*' }} | "
        "Select-Object -ExpandProperty ProcessId"
    )
    try:
        output = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return []
    pids = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.append(int(line))
        except ValueError:
            continue
    return sorted(set(pids))


def validate_active_release() -> tuple[bool, list[str], dict]:
    issues = []
    details = {}
    if not ACTIVE_RELEASE_PATH.exists():
        issues.append(f"active release missing: {ACTIVE_RELEASE_PATH}")
        return False, issues, details
    try:
        manifest = json.loads(ACTIVE_RELEASE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(f"active release unreadable: {exc}")
        return False, issues, details

    required = ["release_id", "model_path", "scaler_path", "metadata_path", "metrics_path", "activated_at"]
    missing = [key for key in required if not manifest.get(key)]
    if missing:
        issues.append(f"active release missing keys: {missing}")
        return False, issues, details

    details["release_id"] = manifest["release_id"]
    details["activated_at"] = manifest["activated_at"]
    for key in ["model_path", "scaler_path", "metadata_path", "metrics_path"]:
        candidate = Path(manifest[key])
        if not candidate.is_absolute():
            candidate = WEBAPP_ROOT / "models" / manifest[key]
        if not candidate.exists():
            issues.append(f"{key} missing: {candidate}")
        else:
            details[key] = str(candidate)
    return len(issues) == 0, issues, details


def install_runtime() -> None:
    ensure_venv()
    pip_install(["install", "--upgrade", "pip"])
    pip_install(["install", "-r", str(REQUIREMENTS_PATH)])
    ok, issues, details = validate_active_release()
    if not ok:
        raise RuntimeError("; ".join(issues))
    health_ok, detail = check_health(timeout=1.0)
    if health_ok:
        print(f"BenfordRich detector already healthy with release={detail}")
    else:
        print(f"BenfordRich detector installed. Active release: {details.get('release_id', 'unknown')}")


def print_status() -> int:
    manifest = load_manifest()
    port = int(manifest["sidecar"]["port"])
    release_ok, issues, details = validate_active_release()
    health_ok, health_detail = check_health(timeout=2.0)
    pid = running_pid_for_port(port)
    extra = running_pids_for_port_windows(port)
    all_pids = sorted(set(([pid] if pid else []) + extra))

    print("[BenfordRich Detector]")
    print(f"  venv: {'OK' if PYTHON_BIN.exists() else 'MISSING'} - {PYTHON_BIN}")
    print(f"  active_release: {'OK' if release_ok else 'FAILED'} - {details.get('release_id', 'unknown')}")
    for issue in issues:
        print(f"  ERROR: {issue}")
    print(f"  port_{port}: {'RUNNING' if all_pids else 'STOPPED'}")
    if all_pids:
        print(f"  pid: {', '.join(str(p) for p in all_pids)}")
    print(f"  health: {'OK' if health_ok else 'FAILED'} - {health_detail}")
    return 0 if (PYTHON_BIN.exists() and release_ok and health_ok) else 1


def start_runtime() -> int:
    manifest = load_manifest()
    port = int(manifest["sidecar"]["port"])
    if not PYTHON_BIN.exists():
        print(f"[ERROR] BenfordRich venv missing: {PYTHON_BIN}")
        return 1
    release_ok, issues, _details = validate_active_release()
    if not release_ok:
        print("[ERROR] BenfordRich active release invalid:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    ok, detail = check_health(timeout=2.0)
    if ok:
        print(f"BenfordRich detector already running on port {port} (release={detail})")
        return 0
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_handle = LOG_PATH.open("a", encoding="utf-8")
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [str(PYTHON_BIN), str(SERVER_PATH)],
        cwd=str(WEBAPP_ROOT),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        close_fds=False,
    )
    for _ in range(40):
        time.sleep(1)
        ok, detail = check_health(timeout=2.0)
        if ok:
            print(f"BenfordRich detector started successfully with release={detail}")
            return 0
    print("BenfordRich detector failed to start within timeout.")
    return 1


def stop_runtime() -> int:
    manifest = load_manifest()
    port = int(manifest["sidecar"]["port"])
    pid_candidates = []
    pid = running_pid_for_port(port)
    if pid:
        pid_candidates.append(pid)
    pid_candidates.extend(running_pids_for_port_windows(port))
    pid_candidates.extend(running_server_pids_windows())
    pid_candidates = sorted(set(pid_candidates))
    if not pid_candidates:
        print(f"BenfordRich detector already stopped on port {port}")
        return 0
    for candidate in pid_candidates:
        subprocess.run(["taskkill", "/PID", str(candidate), "/F"], check=False)
    time.sleep(1)
    print(f"BenfordRich detector stopped (pid={', '.join(str(p) for p in pid_candidates)})")
    return 0


def main() -> int:
    args = parse_args()
    if args.mode == "install":
        install_runtime()
        return 0
    if args.mode == "status":
        return print_status()
    if args.mode == "start":
        return start_runtime()
    if args.mode == "stop":
        return stop_runtime()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
