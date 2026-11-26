from appium import webdriver
from appium.options.android import UiAutomator2Options

from .env_manager import (adb, ensure_app_installed, ensure_appium, ensure_emulator,
                          load_caps_file, online_emulators)


def create_driver():
    """Start emulator + Appium if needed, then launch the app with capabilities.json."""
    conf = load_caps_file()
    caps = dict(conf["capabilities"])
    pkg = caps.get("appium:appPackage", "")
    if not caps.get("appium:app") and (not pkg or pkg.startswith("TODO")):
        raise RuntimeError("Set 'appium:appPackage' in config/capabilities.json "
                           "(find it with: python -m src.list_apps)")

    serial = ensure_emulator(conf["emulator"])
    ensure_appium(conf["appium"])
    if not caps.get("appium:app"):
        ensure_app_installed(serial, pkg)

    caps.setdefault("appium:udid", serial)
    caps.setdefault("appium:deviceName", serial)
    options = UiAutomator2Options().load_capabilities(caps)
    return webdriver.Remote(conf["appium"]["server_url"], options=options)


def get_serial(driver) -> str:
    return driver.capabilities.get("deviceUDID") or online_emulators()[0]
