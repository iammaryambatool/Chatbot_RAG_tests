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
DE_RESULTS: list[dict] = []


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


@pytest.fixture(scope="session")
def get_reply(chatbot):
    """Ask the bot once per question; both test files share the cached reply."""
    cache = {}

    def _get(question):
        if question not in cache:
            cache[question] = chatbot.ask(question)
        return cache[question]
    return _get


@pytest.fixture(scope="session")
def deepeval_evaluator(cfg):
    from src.deepeval_metrics import DeepEvalEvaluator
    return DeepEvalEvaluator(cfg["deepeval"]["thresholds"])


@pytest.fixture(scope="session")
def record_deepeval():
    return DE_RESULTS.append


def pytest_generate_tests(metafunc):
    if "case" in metafunc.fixturenames:
        cfg = load_config()
        with open(ROOT / cfg["evaluation"]["data_file"], encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        metafunc.parametrize("case", rows, ids=[r["id"] for r in rows])


def pytest_sessionfinish(session, exitstatus):
    out = ROOT / "reports"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if DE_RESULTS:
        out.mkdir(exist_ok=True)
        with open(out / f"deepeval_results_{stamp}.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(DE_RESULTS[0].keys()))
            w.writeheader()
            w.writerows(DE_RESULTS)
        de = {}
        for m in ("de_answer_relevancy", "de_correctness", "de_faithfulness"):
            vals = [r[m] for r in DE_RESULTS if r[m] is not None]
            de[m] = round(sum(vals) / len(vals), 3) if vals else None
        de["pass_rate"] = round(sum(r["passed"] for r in DE_RESULTS) / len(DE_RESULTS), 3)
        (out / f"deepeval_summary_{stamp}.json").write_text(json.dumps(de, indent=2))
        print(f"\n=== DeepEval summary ===\n{json.dumps(de, indent=2)}")
    if not RESULTS:
        return
    out.mkdir(exist_ok=True)
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
