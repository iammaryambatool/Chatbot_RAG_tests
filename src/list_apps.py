"""List installed apps on the emulator to find your app's package name.

    python -m src.list_apps          # user-installed apps
    python -m src.list_apps chat     # search all apps (incl. system) for 'chat'
"""
import sys

from .config import load_config  # noqa: F401  (loads .env)
from .env_manager import adb, ensure_emulator, load_caps_file


def main():
    serial = ensure_emulator(load_caps_file()["emulator"])
    term = sys.argv[1] if len(sys.argv) > 1 else None
    out = adb("shell", "pm", "list", "packages", *([] if term else ["-3"]), serial=serial)
    for line in sorted(out.splitlines()):
        pkg = line.replace("package:", "")
        if not term or term.lower() in pkg.lower():
            print(pkg)


if __name__ == "__main__":
    main()
