"""Helpers for reading Appium's page_source XML (UiAutomator2 hierarchy)."""
import re
import xml.etree.ElementTree as ET

BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def bounds(el: ET.Element):
    m = BOUNDS_RE.match(el.attrib.get("bounds", ""))
    return tuple(int(v) for v in m.groups()) if m else None


def area(b) -> int:
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def is_labelled(el: ET.Element) -> bool:
    a = el.attrib
    return bool(a.get("resource-id") or a.get("text") or a.get("content-desc"))


def element_at(root: ET.Element, x: float, y: float, screen_area: int):
    """Best element for a tap at (x, y): smallest labelled element under the point.
    Returns None if only unlabelled/huge containers are there (-> coordinate fallback)."""
    hits = []
    for el in root.iter():
        b = bounds(el)
        if b and area(b) > 0 and b[0] <= x <= b[2] and b[1] <= y <= b[3]:
            hits.append((area(b), el))
    hits.sort(key=lambda t: t[0])
    for a, el in hits:
        if is_labelled(el) and a < 0.6 * screen_area:
            return el
    return None


def _count(root, attr, value) -> int:
    return sum(1 for e in root.iter() if e.attrib.get(attr) == value)


def locators_for(root: ET.Element, el: ET.Element) -> list[dict]:
    """Ordered locator candidates for an element (most stable first)."""
    a = el.attrib
    rid, desc, text = a.get("resource-id", ""), a.get("content-desc", ""), a.get("text", "")
    out = []
    if rid:
        n = _count(root, "resource-id", rid)
        if n == 1:
            out.append({"by": "id", "value": rid})
        elif text and '"' not in text:
            out.append({"by": "xpath", "value": f'//*[@resource-id="{rid}" and @text="{text}"]'})
        else:
            same = [e for e in root.iter() if e.attrib.get("resource-id") == rid]
            out.append({"by": "xpath", "value": f'(//*[@resource-id="{rid}"])[{same.index(el) + 1}]'})
    if desc and _count(root, "content-desc", desc) == 1:
        out.append({"by": "desc", "value": desc})
    if text and _count(root, "text", text) == 1:
        out.append({"by": "text", "value": text})
    return out


def label_of(el: ET.Element | None) -> str:
    if el is None:
        return "(unlabelled area)"
    a = el.attrib
    return a.get("text") or a.get("content-desc") or a.get("resource-id", "").split("/")[-1] or "?"
