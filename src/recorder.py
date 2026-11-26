"""Record the path to the chatbot by doing it by hand in the emulator.

    python -m src.recorder

1. The emulator + Appium start (if needed) and your app launches.
2. PHASE 1 - tap through the app to the chatbot screen with the mouse. Each tap is
   captured and printed. Wait ~2s between taps. Don't use the keyboard in this phase.
   Type `undo` + Enter to drop the last step, or just Enter when you're on the chat screen.
3. PHASE 2 - calibration: send one message to the bot and wait for its reply. The recorder
   works out the input box, send button and bot-message locators from what changed.
Result: flows/chatbot_flow.json (replayed by the tests).
"""
import json
import sys
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter, deque
from datetime import datetime

from .config import FLOW_FILE, ROOT
from .driver import create_driver, get_serial
from .touch import TouchListener, display_size
from .uitree import bounds, element_at, label_of, locators_for


class Snapshotter(threading.Thread):
    """Keeps taking UI-hierarchy snapshots so we know what was on screen *before* each tap."""

    def __init__(self, driver):
        super().__init__(daemon=True)
        self.driver, self.snaps, self.running = driver, deque(maxlen=8), True

    def run(self):
        while self.running:
            t = time.time()
            try:
                self.snaps.append((t, self.driver.page_source))
            except Exception:
                time.sleep(0.5)

    def before(self, t: float):
        older = [s for s in self.snaps if s[0] <= t]
        return older[-1] if older else (self.snaps[0] if self.snaps else (0, None))

    def latest(self):
        return self.snaps[-1][1] if self.snaps else None


def _edit_texts(root):
    return [e for e in root.iter() if e.attrib.get("class", "").endswith("EditText")]


def main():
    sys.stdout.reconfigure(errors="replace")
    driver = create_driver()
    try:
        driver.update_settings({"waitForIdleTimeout": 0})
    except Exception:
        pass
    serial = get_serial(driver)
    w, h = display_size(serial)
    screen_area = w * h
    snap = Snapshotter(driver)
    snap.start()
    time.sleep(3)

    steps, calib, mode = [], [], {"v": "flow"}
    (ROOT / "flows" / "debug").mkdir(parents=True, exist_ok=True)

    def on_touch(kind, s, e, t_down):
        _, xml = snap.before(t_down)
        if not xml:
            return
        root = ET.fromstring(xml)
        if kind == "swipe":
            step = {"action": "swipe", "label": "swipe",
                    "start": [round(s[0] / w, 4), round(s[1] / h, 4)],
                    "end": [round(e[0] / w, 4), round(e[1] / h, 4)]}
            info = {"cls": "", "cy": s[1], "edits": []}
            desc = "swipe"
        else:
            el = element_at(root, s[0], s[1], screen_area)
            step = {"action": "tap", "label": label_of(el),
                    "locators": locators_for(root, el) if el is not None else [],
                    "x_pct": round(s[0] / w, 4), "y_pct": round(s[1] / h, 4)}
            info = {"cls": el.attrib.get("class", "") if el is not None else "", "cy": s[1],
                    "edits": [bounds(x) for x in _edit_texts(root)]}
            loc = step["locators"][0] if step["locators"] else None
            desc = f"tap '{step['label']}'" + (f"  [{loc['by']}={loc['value']}]" if loc else "  [coordinates only]")
        if mode["v"] == "flow":
            steps.append(step)
            print(f"  step {len(steps)}: {desc}")
        else:
            calib.append((step, info))

    listener = TouchListener(serial, (w, h), on_touch)
    if not listener.ranges:
        print("Could not find the emulator's touch device (getevent). Cannot record.")
        driver.quit()
        return
    listener.start()

    print("\n=== PHASE 1: navigate to the chatbot ===")
    print("Tap through the app in the emulator window until you are on the chat screen.")
    print("Commands: Enter = finished, 'undo' = remove last step\n")
    while True:
        cmd = input().strip().lower()
        if cmd == "undo" and steps:
            print(f"  removed step {len(steps)}")
            steps.pop()
        elif cmd in ("", "done"):
            break

    # ---------------- phase 2: calibration
    mode["v"] = "calib"
    time.sleep(2)
    xml_a = snap.latest()
    print("\n=== PHASE 2: calibrate the chat locators ===")
    print("In the emulator: tap the message box, type a short message, press SEND,")
    print("and wait until the bot's reply is fully shown.")
    sent = input("Type here the exact message you sent, then press Enter: ").strip()
    time.sleep(2)
    xml_b = snap.latest()
    listener.stop()
    snap.running = False

    root_a, root_b = ET.fromstring(xml_a), ET.fromstring(xml_b)
    (ROOT / "flows" / "debug" / "screen_before_send.xml").write_text(xml_a, encoding="utf-8")
    (ROOT / "flows" / "debug" / "screen_after_reply.xml").write_text(xml_b, encoding="utf-8")
    chatbot = {"input_field": None, "send_button": None, "bot_messages": None}

    # input field: the EditText on the chat screen
    edits = _edit_texts(root_a)
    if edits:
        el = edits[0]
        locs = locators_for(root_a, el)
        chatbot["input_field"] = locs[0] if locs else {"by": "xpath", "value": "(//android.widget.EditText)[1]"}

    # send button: last tap on the same row as the message box (not the box itself)
    for step, info in reversed(calib):
        if step["action"] != "tap" or info["cls"].endswith("EditText") or not step["locators"]:
            continue
        if any(b and b[1] <= info["cy"] <= b[3] for b in info["edits"]):
            chatbot["send_button"] = step["locators"][0]
            break
    if not chatbot["send_button"]:
        for step, _ in reversed(calib):
            if any(k in (l["value"] or "").lower() for l in step.get("locators", []) for k in ("send", "submit")):
                chatbot["send_button"] = step["locators"][0]
                break

    # bot messages: new text elements that appeared after sending (excluding what we typed)
    before = Counter((e.attrib.get("resource-id", ""), e.attrib.get("class", ""), e.attrib.get("text", ""))
                     for e in root_a.iter() if e.attrib.get("text"))
    new, user_groups = [], set()
    for e in root_b.iter():
        a = e.attrib
        if not a.get("text") or a.get("class", "").endswith("EditText"):
            continue
        sig = (a.get("resource-id", ""), a.get("class", ""), a["text"])
        if sent and a["text"].strip() == sent:
            user_groups.add(sig[:2])
        if before[sig] > 0:
            before[sig] -= 1
        elif not (sent and a["text"].strip() == sent):
            new.append(e)
    groups: dict[tuple, list] = {}
    for e in new:
        groups.setdefault((e.attrib.get("resource-id", ""), e.attrib.get("class", "")), []).append(e)
    warnings = []
    if groups:
        (rid, cls), els = max(groups.items(), key=lambda kv: sum(len(x.attrib["text"]) for x in kv[1]))
        print(f"\nBot reply detected: \"{els[-1].attrib['text'][:80]}\"")
        if rid:
            chatbot["bot_messages"] = {"by": "id", "value": rid}
            if (rid, cls) in user_groups:
                warnings.append("Your message and the bot's reply share the same resource-id, so "
                                "'bot_messages' would also match YOUR bubbles. Edit it by hand "
                                "(see flows/debug/screen_after_reply.xml).")
        else:
            warnings.append("The bot's bubbles have no resource-id. Set chatbot.bot_messages by hand "
                            "(xpath / uiselector); see flows/debug/screen_after_reply.xml.")
    else:
        warnings.append("No new text appeared after sending. Was the reply visible? Re-run the recorder.")

    flow = {"recorded_at": datetime.now().isoformat(timespec="seconds"),
            "package": driver.capabilities.get("appPackage") or driver.current_package,
            "navigation": steps, "chatbot": chatbot}
    FLOW_FILE.parent.mkdir(exist_ok=True)
    FLOW_FILE.write_text(json.dumps(flow, indent=2), encoding="utf-8")
    driver.quit()

    print(f"\nSaved {FLOW_FILE}")
    print(f"  navigation steps : {len(steps)}")
    for k, v in chatbot.items():
        print(f"  {k:13}: {v if v else 'NOT FOUND - set it by hand in the flow file'}")
    for msg in warnings:
        print(f"  WARNING: {msg}")


if __name__ == "__main__":
    main()
