import csv
import json
from datetime import datetime

import pytest

from src.chatbot_page import ChatbotPage
from src.config import ROOT, load_config
from src.driver import create_driver
from src.metrics import Evaluator
from src.navigator import navigate_to_chatbot

RESULTS: list[dict] = []


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def test_cases(cfg):
    with open(ROOT / cfg["evaluation"]["data_file"], encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="session")
def chatbot(cfg):
    driver = create_driver()
    navigate_to_chatbot(driver, cfg)
    yield ChatbotPage(driver, cfg)
    driver.quit()


@pytest.fixture(scope="session")
def evaluator():
    return Evaluator()


@pytest.fixture(scope="session")
def record():
    return RESULTS.append


def pytest_generate_tests(metafunc):
    if "case" in metafunc.fixturenames:
        cfg = load_config()
        with open(ROOT / cfg["evaluation"]["data_file"], encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        metafunc.parametrize("case", rows, ids=[r["id"] for r in rows])


def pytest_sessionfinish(session, exitstatus):
    if not RESULTS:
        return
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cols = list(RESULTS[0].keys())
    with open(out / f"results_{stamp}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(RESULTS)
    metrics = ["correctness", "relevance", "faithfulness", "similarity", "latency_s"]
    summary = {m: round(sum(r[m] for r in RESULTS) / len(RESULTS), 3) for m in metrics}
    summary["pass_rate"] = round(sum(r["passed"] for r in RESULTS) / len(RESULTS), 3)
    (out / f"summary_{stamp}.json").write_text(json.dumps(summary, indent=2))
    print(f"\n=== Chatbot eval summary ===\n{json.dumps(summary, indent=2)}\nReports in {out}")
