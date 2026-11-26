from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"')


def to_locator(by: str, value: str) -> tuple[str, str]:
    """Turn the short names used in config/flow files into an Appium (strategy, value) pair."""
    if by == "text":
        return AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{_esc(value)}")'
    if by == "textContains":
        return AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{_esc(value)}")'
    if by == "id":
        return AppiumBy.ID, value
    if by == "xpath":
        return AppiumBy.XPATH, value
    if by == "desc":
        return AppiumBy.ACCESSIBILITY_ID, value
    if by == "uiselector":
        return AppiumBy.ANDROID_UIAUTOMATOR, value
    raise ValueError(f"Unknown locator type: {by}")


def wait_for(driver, loc: dict, timeout: int = 15, clickable: bool = False):
    strategy, value = to_locator(loc["by"], loc["value"])
    cond = EC.element_to_be_clickable if clickable else EC.presence_of_element_located
    return WebDriverWait(driver, timeout).until(cond((strategy, value)))


def find_all(driver, loc: dict):
    strategy, value = to_locator(loc["by"], loc["value"])
    return driver.find_elements(strategy, value)
