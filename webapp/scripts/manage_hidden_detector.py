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
MUN_REQUIREMENTS = HIDDEN_ROOT / "requirements.txt"
MUN_SERVER = HIDDEN_ROOT / "server.py"
MUN_VENDOR_ROOT = HIDDEN_ROOT / "upstream_vendor"
MUN_MODELS_ROOT = WEBAPP_ROOT / "models" / "hidden_detectors" / "mun"
MUN_WEIGHTS_ROOT = MUN_MODELS_ROOT / "weights"
MUN_OUTPUT_ROOT = MUN_MODELS_ROOT / "outputs"
LOG_PATH = WEBAPP_ROOT / "hidden_detector_mun.log"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage hidden MUN detector runtime.")
    parser.add_argument("mode", choices=["install", "status", "start", "stop"])
    return parser.parse_args()


def load_manifest() -> dict:
    return json.loads(MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))


def ensure_venv() -> None:
    if MUN_PYTHON.exists():
        return
    subprocess.run([sys.executable, "-m", "venv", str(MUN_VENV)], check=True)


def pip_install(args: list[str]) -> None:
    subprocess.run([str(MUN_PYTHON), "-m", "pip", *args], check=True)


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


def install_runtime() -> None:
    ensure_venv()
    pip_install(["install", "--upgrade", "pip"])
    pip_install(["install", "-r", str(MUN_REQUIREMENTS)])

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
    ok, detail = check_health(timeout=2.0)

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
    print(f"  port_{port}: {'RUNNING' if pid else 'STOPPED'}")
    if pid:
        print(f"  pid: {pid}")
    print(f"  health: {'OK' if ok else 'FAILED'} - {detail}")
    return 0 if (MUN_PYTHON.exists() and ok) else 1


def start_runtime() -> int:
    manifest = load_manifest()
    port = int(manifest["sidecar"]["port"])
    if not MUN_PYTHON.exists():
        print(f"[ERROR] Hidden detector venv missing: {MUN_PYTHON}")
        return 1

    # Keep the vendored mmseg patches in sync on every start so machines that only
    # pull code changes do not keep stale site-packages copies.
    copy_vendor_tree()

    ok, _detail = check_health(timeout=2.0)
    if ok:
        print(f"Hidden detector already running on port {port}")
        return 0

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_handle = LOG_PATH.open("a", encoding="utf-8")
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    subprocess.Popen(
        [str(MUN_PYTHON), str(MUN_SERVER)],
        cwd=str(WEBAPP_ROOT),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        close_fds=False,
    )

    for _ in range(60):
        time.sleep(1)
        ok, detail = check_health(timeout=2.0)
        if ok:
            print(f"Hidden detector started successfully on device={detail}")
            return 0

    print("Hidden detector failed to start within timeout.")
    return 1


def stop_runtime() -> int:
    manifest = load_manifest()
    port = int(manifest["sidecar"]["port"])
    pid = running_pid_for_port(port)
    if not pid:
        print(f"Hidden detector already stopped on port {port}")
        return 0

    subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
    time.sleep(1)
    print(f"Hidden detector stopped (pid={pid})")
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
