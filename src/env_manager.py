"""Starts what the tests need: Android emulator + Appium server (only if not already running)."""
import atexit
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .config import ROOT

CAPS_FILE = ROOT / "config" / "capabilities.json"


def load_caps_file() -> dict:
    return json.loads(CAPS_FILE.read_text(encoding="utf-8"))


def adb(*args: str, serial: str | None = None, timeout: int = 30) -> str:
    cmd = ["adb"] + (["-s", serial] if serial else []) + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()


def online_emulators() -> list[str]:
    lines = adb("devices").splitlines()
    return [l.split()[0] for l in lines if l.startswith("emulator-") and l.split()[-1] == "device"]


# ---------------------------------------------------------------- emulator
def ensure_emulator(emu: dict) -> str:
    """Return the serial of a booted emulator, starting one if needed."""
    running = online_emulators()
    if running:
        return running[0]
    if not emu.get("auto_start", True):
        raise RuntimeError("No emulator is running and emulator.auto_start is false.")

    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    exe = Path(sdk) / "emulator" / "emulator.exe" if sdk else None
    if not exe or not exe.exists():
        exe = shutil.which("emulator")
    if not exe:
        raise RuntimeError("Cannot find the Android emulator. Set ANDROID_HOME.")

    args = [str(exe), "-avd", emu["avd_name"], "-no-snapshot-save"]
    if emu.get("headless"):
        args += ["-no-window", "-no-audio"]
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    print(f"[env] Starting emulator '{emu['avd_name']}' ...")
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)

    deadline = time.time() + emu.get("boot_timeout_s", 300)
    while time.time() < deadline:
        for serial in online_emulators():
            if adb("shell", "getprop", "sys.boot_completed", serial=serial) == "1":
                print(f"[env] Emulator ready: {serial}")
                time.sleep(3)  # let launcher settle
                return serial
        time.sleep(3)
    raise RuntimeError(f"Emulator '{emu['avd_name']}' did not boot within the timeout.")


# ----------------------------------------------------------------- appium
def _appium_up(url: str) -> bool:
    try:
        urllib.request.urlopen(url.rstrip("/") + "/status", timeout=2)
        return True
    except Exception:
        return False


def ensure_appium(app: dict) -> None:
    url = app["server_url"]
    if _appium_up(url):
        return
    if not app.get("auto_start", True):
        raise RuntimeError(f"Appium is not running at {url} and appium.auto_start is false.")
    exe = shutil.which("appium")
    if not exe:
        raise RuntimeError("`appium` not found on PATH. Install with: npm i -g appium")

    u = urlparse(url)
    log_dir = ROOT / "reports"
    log_dir.mkdir(exist_ok=True)
    log = open(log_dir / "appium.log", "w", encoding="utf-8")
    print(f"[env] Starting Appium on {url} ...")
    proc = subprocess.Popen([exe, "--address", u.hostname or "127.0.0.1", "--port", str(u.port or 4723)],
                            stdout=log, stderr=subprocess.STDOUT)

    def _kill():
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.terminate()
    atexit.register(_kill)

    for _ in range(60):
        if _appium_up(url):
            return
        time.sleep(1)
    raise RuntimeError("Appium did not start in 60s. See reports/appium.log")


def ensure_app_installed(serial: str, package: str) -> None:
    out = adb("shell", "pm", "list", "packages", package, serial=serial)
    if f"package:{package}" not in out.splitlines():
        raise RuntimeError(
            f"App '{package}' is not installed on {serial}. Install the APK "
            f"(drag it onto the emulator or `adb install app.apk`), or set 'appium:app' "
            f"in config/capabilities.json to the APK path. "
            f"Run `python -m src.list_apps` to see installed packages.")
