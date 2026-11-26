"""Replays the flow recorded by `python -m src.recorder`."""
import time

from selenium.common.exceptions import TimeoutException

from .locators import wait_for

SETTLE_S = 1.0


def _tap(driver, step: dict, n: int) -> None:
    for i, loc in enumerate(step.get("locators", [])):
        try:
            wait_for(driver, loc, timeout=15 if i == 0 else 3, clickable=True).click()
            return
        except TimeoutException:
            continue
    # Last resort: tap the recorded screen position
    if "x_pct" in step:
        size = driver.get_window_size()
        print(f"[nav] step {n}: no locator matched, tapping recorded coordinates")
        driver.execute_script("mobile: clickGesture", {
            "x": int(step["x_pct"] * size["width"]), "y": int(step["y_pct"] * size["height"])})
        return
    raise RuntimeError(f"Navigation step {n} failed: {step.get('label')} - nothing matched")


def _swipe(driver, step: dict) -> None:
    size = driver.get_window_size()
    w, h = size["width"], size["height"]
    driver.execute_script("mobile: dragGesture", {
        "startX": int(step["start"][0] * w), "startY": int(step["start"][1] * h),
        "endX": int(step["end"][0] * w), "endY": int(step["end"][1] * h),
        "speed": 1500})


def navigate_to_chatbot(driver, cfg: dict) -> None:
    if not cfg.get("flow_loaded"):
        raise RuntimeError("No recorded flow found (flows/chatbot_flow.json). "
                           "Run:  python -m src.recorder")
    time.sleep(2)  # let the app finish launching
    for n, step in enumerate(cfg["navigation"], start=1):
        if step["action"] == "tap":
            _tap(driver, step, n)
        elif step["action"] == "swipe":
            _swipe(driver, step)
        time.sleep(SETTLE_S)

    # Confirm we actually landed on the chatbot screen
    try:
        wait_for(driver, cfg["chatbot"]["input_field"], timeout=20)
    except TimeoutException:
        raise RuntimeError("Replayed the flow but the chat input field was not found. "
                           "Re-record the flow or fix chatbot.input_field.") from None
