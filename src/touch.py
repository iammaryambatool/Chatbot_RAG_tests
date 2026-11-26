"""Capture taps/swipes made by hand in the emulator, via `adb shell getevent`."""
import re
import subprocess
import threading
import time

from .env_manager import adb

SWIPE_MIN_PX = 40


def display_size(serial: str) -> tuple[int, int]:
    out = adb("shell", "wm", "size", serial=serial)
    if "Override size" in out:
        out = out.split("Override size:")[-1]
    w, h = re.search(r"(\d+)x(\d+)", out).groups()
    return int(w), int(h)


def touch_ranges(serial: str) -> dict[str, tuple[int, int]]:
    """Raw max X/Y of each touch input device (needed to scale to pixels)."""
    out = adb("shell", "getevent", "-lp", serial=serial, timeout=20)
    ranges = {}
    for block in re.split(r"add device \d+: ", out)[1:]:
        dev = block.split()[0]
        mx = re.search(r"ABS_MT_POSITION_X\s*:.*?max (\d+)", block)
        my = re.search(r"ABS_MT_POSITION_Y\s*:.*?max (\d+)", block)
        if mx and my:
            ranges[dev] = (int(mx.group(1)), int(my.group(1)))
    return ranges


class TouchListener(threading.Thread):
    """Calls callback(kind, (x0,y0), (x1,y1), t_down) with pixel coords; kind = 'tap' | 'swipe'."""

    def __init__(self, serial: str, size: tuple[int, int], callback, ranges=None):
        super().__init__(daemon=True)
        self.size, self.cb = size, callback
        self.serial = serial
        self.ranges = ranges if ranges is not None else touch_ranges(serial)
        self.state: dict[str, dict] = {}
        self.proc = None

    def run(self):
        self.proc = subprocess.Popen(["adb", "-s", self.serial, "shell", "getevent", "-l"],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, bufsize=1)
        for line in self.proc.stdout:
            self.feed_line(line)

    def stop(self):
        if self.proc:
            self.proc.terminate()

    def feed_line(self, line: str) -> None:
        parts = line.split()
        if len(parts) < 4:
            return
        dev, code, val = parts[0].rstrip(":"), parts[2], parts[3]
        if dev not in self.ranges:
            return
        st = self.state.setdefault(dev, {"x": 0, "y": 0, "pending": False, "start": None, "t": 0.0})
        if code == "ABS_MT_POSITION_X":
            st["x"] = int(val, 16)
        elif code == "ABS_MT_POSITION_Y":
            st["y"] = int(val, 16)
        elif (code == "BTN_TOUCH" and val == "DOWN") or (code == "ABS_MT_TRACKING_ID" and val != "ffffffff"):
            if st["start"] is None and not st["pending"]:
                st["pending"], st["t"] = True, time.time()
        elif code == "SYN_REPORT" and st["pending"]:
            st["pending"], st["start"] = False, (st["x"], st["y"])
        elif (code == "BTN_TOUCH" and val == "UP") or (code == "ABS_MT_TRACKING_ID" and val == "ffffffff"):
            if st["start"] is not None:
                mx, my = self.ranges[dev]
                to_px = lambda p: (p[0] / mx * self.size[0], p[1] / my * self.size[1])
                s, e = to_px(st["start"]), to_px((st["x"], st["y"]))
                moved = ((s[0] - e[0]) ** 2 + (s[1] - e[1]) ** 2) ** 0.5
                self.cb("swipe" if moved > SWIPE_MIN_PX else "tap", s, e, st["t"])
                st["start"] = None
