from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


WEBAPP_ROOT = Path(__file__).resolve().parents[1]
HIDDEN_ROOT = WEBAPP_ROOT / "hidden_detectors" / "mun"
MODEL_MANIFEST_PATH = HIDDEN_ROOT / "model_manifest.json"
MUN_VENV = WEBAPP_ROOT / ".venv-mun"
MUN_PYTHON = MUN_VENV / "Scripts" / "python.exe"
MUN_VENV_CFG = MUN_VENV / "pyvenv.cfg"
MUN_REQUIREMENTS = HIDDEN_ROOT / "requirements.txt"
MUN_SERVER = HIDDEN_ROOT / "server.py"
MUN_VENDOR_ROOT = HIDDEN_ROOT / "upstream_vendor"
MUN_MODELS_ROOT = WEBAPP_ROOT / "models" / "hidden_detectors" / "mun"
MUN_WEIGHTS_ROOT = MUN_MODELS_ROOT / "weights"
MUN_OUTPUT_ROOT = MUN_MODELS_ROOT / "outputs"
LOG_PATH = WEBAPP_ROOT / "hidden_detector_mun.log"
REQUIRED_RUNTIME_IMPORTS = {
    "flask": "Flask==3.0.3",
    "gdown": "gdown==5.2.1",
    "ftfy": "ftfy==6.2.3",
    "torch": "torch==2.0.1",
    "torchvision": "torchvision==0.15.2",
    "numpy": "numpy==1.24.4",
    "cv2": "opencv-python-headless==4.9.0.80",
    "PIL": "Pillow==9.5.0",
    "mmengine": "mmengine==0.10.4",
}
STARTUP_DEADLINE_SECONDS = 180
HEALTH_RETRY_INTERVAL_SECONDS = 2
HEALTH_START_TIMEOUT_SECONDS = 5.0
HEALTH_STATUS_TIMEOUT_SECONDS = 2.0
LOG_TAIL_LINES = 40


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage hidden MUN detector runtime.")
    parser.add_argument("mode", choices=["install", "status", "start", "stop"])
    return parser.parse_args()


def load_manifest() -> dict:
    return json.loads(MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))


def ensure_venv() -> None:
    if MUN_PYTHON.exists() and MUN_VENV_CFG.exists():
        return
    if MUN_VENV.exists():
        print("Detected broken hidden detector venv. Rebuilding .venv-mun...")
        _remove_venv_tree(MUN_VENV)
    subprocess.run([sys.executable, "-m", "venv", str(MUN_VENV)], check=True)
    if not (MUN_PYTHON.exists() and MUN_VENV_CFG.exists()):
        raise RuntimeError(f"Failed to create a healthy hidden detector venv at {MUN_VENV}")


def _remove_venv_tree(path: Path) -> None:
    if not path.exists():
        return

    errors: list[str] = []
    commands = []
    if os.name == "nt":
        commands.append(["cmd", "/c", "rmdir", "/s", "/q", str(path)])
        commands.append(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Remove-Item -LiteralPath '{str(path)}' -Recurse -Force -ErrorAction Stop",
            ]
        )
    else:
        commands.append(["rm", "-rf", str(path)])

    for cmd in commands:
        try:
            subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=30,
            )
        except Exception as exc:
            errors.append(f"{cmd[0]}: {exc}")
        if not path.exists():
            return

    if path.exists():
        raise RuntimeError(
            "Unable to remove broken hidden detector venv at "
            f"{path}. Close any remaining python/Flask processes that use .venv-mun and retry. "
            + (" Errors: " + "; ".join(errors) if errors else "")
        )


def pip_install(args: list[str]) -> None:
    subprocess.run([str(MUN_PYTHON), "-m", "pip", *args], check=True)


def can_import(module_name: str) -> bool:
    probe = "import importlib, sys; importlib.import_module(sys.argv[1]); print('OK')"
    result = subprocess.run(
        [str(MUN_PYTHON), "-c", probe, module_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    return result.returncode == 0


def ensure_required_runtime_imports() -> None:
    missing_packages = [
        package_spec
        for module_name, package_spec in REQUIRED_RUNTIME_IMPORTS.items()
        if not can_import(module_name)
    ]
    if not missing_packages:
        return

    print(
        "Repairing hidden detector runtime, missing imports: "
        + ", ".join(missing_packages)
    )
    if REQUIRED_RUNTIME_IMPORTS["cv2"] in missing_packages:
        pip_install(["install", "--force-reinstall", "--no-cache-dir", REQUIRED_RUNTIME_IMPORTS["numpy"]])
        pip_install(
            [
                "install",
                "--force-reinstall",
                "--no-cache-dir",
                "--no-deps",
                REQUIRED_RUNTIME_IMPORTS["cv2"],
            ]
        )
        missing_packages = [pkg for pkg in missing_packages if pkg != REQUIRED_RUNTIME_IMPORTS["cv2"]]

    if missing_packages:
        pip_install(["install", "--force-reinstall", "--no-cache-dir", *missing_packages])

    still_missing = [
        package_spec
        for module_name, package_spec in REQUIRED_RUNTIME_IMPORTS.items()
        if not can_import(module_name)
    ]
    if still_missing:
        raise RuntimeError(
            "Hidden detector runtime is still missing required packages after repair: "
            + ", ".join(still_missing)
        )


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if "drive.google.com" in url:
        subprocess.run(
            [
                str(MUN_PYTHON),
                "-m",
                "gdown",
                "--fuzzy",
                url,
                "-O",
                str(destination),
            ],
            check=True,
        )
        return

    with urllib.request.urlopen(url) as response, destination.open("wb") as f:
        shutil.copyfileobj(response, f)


def ensure_weight(entry: dict) -> Path:
    target = MUN_WEIGHTS_ROOT / entry["expected_file_name"]
    expected_hash = entry["sha256"]
    if target.exists() and sha256_of(target) == expected_hash:
        return target

    if target.exists():
        target.unlink()

    download_file(entry["download_url"], target)
    actual_hash = sha256_of(target)
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"Checksum mismatch for {target.name}: got={actual_hash} expected={expected_hash}"
        )
    return target


def copy_vendor_tree() -> None:
    if not MUN_PYTHON.exists():
        raise FileNotFoundError(f"MUN venv missing: {MUN_PYTHON}")

    candidates = [
        MUN_VENV / "Lib" / "site-packages",
        MUN_VENV / "lib" / "site-packages",
    ]
    site_packages = next((p for p in candidates if p.exists()), None)
    if site_packages is None:
        raise FileNotFoundError(
            "Unable to locate .venv-mun site-packages directory. "
            "Expected one of: " + ", ".join(str(p) for p in candidates)
        )
    for source in MUN_VENDOR_ROOT.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(MUN_VENDOR_ROOT)
        destination = site_packages / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    for pycache_dir in (site_packages / "mmseg").rglob("__pycache__"):
        shutil.rmtree(pycache_dir, ignore_errors=True)


def health_url() -> str:
    manifest = load_manifest()
    return f"http://{manifest['sidecar']['host']}:{manifest['sidecar']['port']}/health"


def check_health(timeout: float = 5.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(health_url(), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok"):
            return True, payload.get("device", "unknown")
        return False, payload.get("error") or "health check failed"
    except Exception as exc:
        return False, str(exc)


def tail_log_lines(max_lines: int = LOG_TAIL_LINES) -> str:
    if not LOG_PATH.exists():
        return ""
    try:
        lines = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    return "\n".join(lines[-max_lines:])


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


def running_mun_server_pids_windows() -> list[int]:
    if os.name != "nt":
        return []
    server_marker = str(MUN_SERVER).replace("\\", "\\\\")
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
            timeout=5,
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


def install_runtime() -> None:
    ensure_venv()
    pip_install(["install", "--upgrade", "pip"])
    pip_install(["install", "-r", str(MUN_REQUIREMENTS)])
    ensure_required_runtime_imports()

    manifest = load_manifest()
    ensure_weight(manifest["checkpoint"])
    ensure_weight(manifest["noiseprint_checkpoint"])
    copy_vendor_tree()

    MUN_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    ok, detail = check_health(timeout=1.0)
    if ok:
        print(f"MUN hidden detector already healthy on device={detail}")
    else:
        print("MUN hidden detector installed; service not started yet.")


def print_status() -> int:
    manifest = load_manifest()
    port = int(manifest["sidecar"]["port"])
    ok, detail = check_health(timeout=HEALTH_STATUS_TIMEOUT_SECONDS)

    print("[Hidden Detector]")
    print(f"  venv: {'OK' if MUN_PYTHON.exists() else 'MISSING'} - {MUN_PYTHON}")
    for name, entry in (
        ("checkpoint", manifest["checkpoint"]),
        ("noiseprint", manifest["noiseprint_checkpoint"]),
    ):
        target = MUN_WEIGHTS_ROOT / entry["expected_file_name"]
        if target.exists():
            valid = sha256_of(target) == entry["sha256"]
            print(f"  {name}: {'OK' if valid else 'INVALID'} - {target.name}")
        else:
            print(f"  {name}: MISSING - {target.name}")
    pid = running_pid_for_port(port)
    extra_pids = running_pids_for_port_windows(port)
    all_pids = sorted(set(([pid] if pid else []) + extra_pids))
    running = bool(all_pids) or ok
    print(f"  port_{port}: {'RUNNING' if running else 'STOPPED'}")
    if all_pids:
        print(f"  pid: {', '.join(str(p) for p in all_pids)}")
    print(f"  health: {'OK' if ok else 'FAILED'} - {detail}")
    return 0 if (MUN_PYTHON.exists() and ok) else 1


def start_runtime() -> int:
    manifest = load_manifest()
    port = int(manifest["sidecar"]["port"])
    if not MUN_PYTHON.exists():
        print(f"[ERROR] Hidden detector venv missing: {MUN_PYTHON}")
        return 1

    try:
        ensure_required_runtime_imports()
    except Exception as exc:
        print(f"[ERROR] Hidden detector runtime import check failed: {exc}")
        return 1

    # Keep the vendored mmseg patches in sync on every start so machines that only
    # pull code changes do not keep stale site-packages copies.
    copy_vendor_tree()

    ok, _detail = check_health(timeout=HEALTH_STATUS_TIMEOUT_SECONDS)
    if ok:
        print(f"Hidden detector already running on port {port}")
        return 0

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_handle = LOG_PATH.open("a", encoding="utf-8")
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(
        [str(MUN_PYTHON), str(MUN_SERVER)],
        cwd=str(WEBAPP_ROOT),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        close_fds=False,
    )
    log_handle.close()

    deadline = time.time() + STARTUP_DEADLINE_SECONDS
    time.sleep(1)
    while time.time() < deadline:
        if process.poll() is not None:
            print(f"Hidden detector exited early with code {process.returncode}.")
            tail = tail_log_lines()
            if tail:
                print("--- Hidden detector log tail ---")
                print(tail)
            return 1

        ok, detail = check_health(timeout=HEALTH_START_TIMEOUT_SECONDS)
        if ok:
            print(f"Hidden detector started successfully on device={detail}")
            return 0
        time.sleep(HEALTH_RETRY_INTERVAL_SECONDS)

    print(f"Hidden detector failed to start within timeout ({STARTUP_DEADLINE_SECONDS}s).")
    tail = tail_log_lines()
    if tail:
        print("--- Hidden detector log tail ---")
        print(tail)
    return 1


def stop_runtime() -> int:
    manifest = load_manifest()
    port = int(manifest["sidecar"]["port"])
    pid_candidates = []
    pid = running_pid_for_port(port)
    if pid:
        pid_candidates.append(pid)
    pid_candidates.extend(running_pids_for_port_windows(port))
    pid_candidates.extend(running_mun_server_pids_windows())
    pid_candidates = sorted(set(pid_candidates))

    if not pid_candidates:
        print(f"Hidden detector already stopped on port {port}")
        return 0

    for candidate in pid_candidates:
        subprocess.run(["taskkill", "/PID", str(candidate), "/F"], check=False)
    time.sleep(1)
    print(f"Hidden detector stopped (pid={', '.join(str(p) for p in pid_candidates)})")
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
