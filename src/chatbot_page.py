import time
from dataclasses import dataclass

from selenium.common.exceptions import StaleElementReferenceException

from .locators import find_all, wait_for


@dataclass
class BotReply:
    text: str
    latency_s: float
    timed_out: bool = False


class ChatbotPage:
    def __init__(self, driver, cfg: dict):
        self.driver = driver
        self.c = cfg["chatbot"]

    def _bot_texts(self) -> list[str]:
        for _ in range(3):
            try:
                return [e.text for e in find_all(self.driver, self.c["bot_messages"]) if e.text]
            except StaleElementReferenceException:
                time.sleep(0.3)  # UI re-rendered mid-read (streaming reply); re-query
        return []

    def _typing_visible(self) -> bool:
        ind = self.c.get("typing_indicator") or {}
        if not ind.get("value"):
            return False
        return bool(find_all(self.driver, ind))

    def ask(self, question: str) -> BotReply:
        """Send a message and wait until the bot's reply is complete (text stable)."""
        before = len(self._bot_texts())

        field = wait_for(self.driver, self.c["input_field"], clickable=True)
        field.click()
        field.clear()
        field.send_keys(question)
        wait_for(self.driver, self.c["send_button"], clickable=True).click()

        start = time.time()
        timeout = self.c.get("response_timeout_s", 45)
        stable_for = self.c.get("stable_for_s", 2)
        last_text, last_change = None, time.time()

        while time.time() - start < timeout:
            texts = self._bot_texts()
            if len(texts) > before:
                current = texts[-1]
                if current != last_text:
                    last_text, last_change = current, time.time()
                elif time.time() - last_change >= stable_for and not self._typing_visible():
                    # latency = time until reply stopped changing, minus the stability wait
                    return BotReply(current, round(last_change - start, 2))
            time.sleep(0.5)

        return BotReply(last_text or "", round(time.time() - start, 2), timed_out=True)
