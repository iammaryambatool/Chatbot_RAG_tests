"""Evaluation metrics.

Judge metrics (1-5, higher is better), scored by a Claude model against ground truth:
  - correctness : does the answer convey the same facts as the ground truth?
  - relevance   : does it actually address the question?
  - faithfulness: is it free of hallucination / contradiction of the ground truth?
Other metrics:
  - similarity  : semantic similarity to the ground truth (0-1), also scored by the judge
  - latency_s   : time to a complete reply
"""
import json
import os
from dataclasses import asdict, dataclass

import anthropic

JUDGE_PROMPT = """You are a strict QA evaluator for a customer-facing chatbot.
Compare the chatbot's ANSWER with the GROUND TRUTH for the QUESTION, using the
REFERENCE SOURCE (the official documents the chatbot is supposed to draw on) to check facts.

Score each from 1 (worst) to 5 (best):
- correctness: facts in ANSWER match GROUND TRUTH and the REFERENCE SOURCE; missing key facts lowers it.
- relevance: ANSWER directly addresses the QUESTION.
- faithfulness: every claim in ANSWER is supported by the REFERENCE SOURCE. Claims that are not in the
  source (invented numbers, prices, rules, times, eligibility) lower it, even if they sound plausible.
  Extra details that ARE in the source and are accurate are fine and must not be penalised.
- similarity: 0.0-1.0, how close ANSWER is in meaning to GROUND TRUTH.
If the ground truth describes expected behaviour (e.g. "politely decline"), judge the behaviour.

ANSWERABLE FROM SOURCES: {answerable}
If "no", the ground truth is the expected behaviour and the answer should not state specifics the
sources do not contain; specific invented facts must give faithfulness 1-2.

Also report gt_check: does the GROUND TRUTH agree with the REFERENCE SOURCE?
"ok" if consistent, "incomplete" if it omits key facts the source gives for this question,
"conflict" if it contradicts the source, "n/a" if the question is not answerable from the sources.

QUESTION: {question}
GROUND TRUTH: {ground_truth}
REFERENCE SOURCE:
{reference}
ANSWER: {answer}

Reply with JSON only:
{{"correctness": int, "relevance": int, "faithfulness": int, "similarity": float, "gt_check": "ok|incomplete|conflict|n/a", "reason": "one short sentence"}}"""


def load_reference(source_key: str = "") -> str:
    """Text of the source document(s) for a case. No key -> all sources (to verify 'not in the docs')."""
    from pathlib import Path
    folder = Path(__file__).resolve().parent.parent / "sources"
    files = [folder / f"{source_key}.txt"] if source_key else sorted(folder.glob("*.txt"))
    return "\n\n".join(f.read_text(encoding="utf-8") for f in files if f.exists()) or "(no source available)"


@dataclass
class Scores:
    correctness: float = 0
    relevance: float = 0
    faithfulness: float = 0
    similarity: float = 0
    latency_s: float = 0
    gt_check: str = ""
    reason: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class Evaluator:
    def __init__(self):
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.judge_model = os.getenv("JUDGE_MODEL", "claude-haiku-5-5")

    def _judge(self, question: str, ground_truth: str, answer: str, answerable: str = "yes",
               reference: str = "") -> dict:
        resp = self.client.messages.create(
            model=self.judge_model,
            max_tokens=400,
            messages=[{"role": "user", "content": JUDGE_PROMPT.format(
                question=question, ground_truth=ground_truth, answer=answer,
                answerable=answerable, reference=reference or "(no source available)")}],
        )
        text = resp.content[0].text
        return json.loads(text[text.index("{"):text.rindex("}") + 1])

    def evaluate(self, question: str, ground_truth: str, answer: str, latency_s: float,
                 answerable: str = "yes", reference: str = "") -> Scores:
        if not answer.strip():
            return Scores(latency_s=latency_s, reason="Empty / no reply from chatbot")
        j = self._judge(question, ground_truth, answer, answerable, reference)
        return Scores(
            correctness=float(j["correctness"]),
            relevance=float(j["relevance"]),
            faithfulness=float(j["faithfulness"]),
            similarity=round(float(j["similarity"]), 3),
            latency_s=latency_s,
            gt_check=str(j.get("gt_check", "")),
            reason=j.get("reason", ""),
        )


def check_thresholds(scores: Scores, thresholds: dict) -> list[str]:
    """Return a list of human-readable failures (empty list = pass)."""
    fails = []
    for m in ("correctness", "relevance", "faithfulness", "similarity"):
        if getattr(scores, m) < thresholds[m]:
            fails.append(f"{m} {getattr(scores, m)} < {thresholds[m]}")
    if scores.latency_s > thresholds["max_latency_s"]:
        fails.append(f"latency {scores.latency_s}s > {thresholds['max_latency_s']}s")
    return fails
