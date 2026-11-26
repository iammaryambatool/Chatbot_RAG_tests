import json
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
FLOW_FILE = ROOT / "flows" / "chatbot_flow.json"
load_dotenv(ROOT / ".env")


def load_config(path: str | Path = ROOT / "config" / "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Merge the recorded flow (navigation steps + chatbot locators), if present
    cfg["navigation"] = []
    cfg["flow_loaded"] = False
    if FLOW_FILE.exists():
        flow = json.loads(FLOW_FILE.read_text(encoding="utf-8"))
        cfg["navigation"] = flow.get("navigation", [])
        for key, loc in (flow.get("chatbot") or {}).items():
            if loc:
                cfg["chatbot"][key] = loc
        cfg["flow_loaded"] = True
    return cfg
