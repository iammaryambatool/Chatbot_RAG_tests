"""Helper to discover locators.

Open the app manually on the emulator to the screen you want to inspect, then run:
    python -m src.inspect_screen
It prints every visible element's text / id / content-desc so you can copy values into config.yaml.
Run it once per screen (home screen, menu, chatbot screen, after sending a message).
"""
import xml.etree.ElementTree as ET

from .driver import create_driver


def main():
    driver = create_driver()
    try:
        root = ET.fromstring(driver.page_source)
        print(f"{'TEXT':35} {'RESOURCE-ID':50} {'CONTENT-DESC':25} CLASS")
        for el in root.iter():
            a = el.attrib
            if a.get("text") or a.get("resource-id") or a.get("content-desc"):
                print(f"{a.get('text','')[:34]:35} {a.get('resource-id','')[:49]:50} "
                      f"{a.get('content-desc','')[:24]:25} {a.get('class','').split('.')[-1]}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
