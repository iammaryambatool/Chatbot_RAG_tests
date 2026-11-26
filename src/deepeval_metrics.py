"""Optional second evaluation using the DeepEval library (kept separate from src/metrics.py).

DeepEval metrics (0-1, higher is better), judged by Claude via a small model wrapper:
  - answer_relevancy : does the answer address the question?
  - faithfulness     : are the answer's claims supported by the source text? (answerable rows only)
  - correctness      : GEval, does the answer match the ground truth?
"""
import json
import os
import re

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")  # no usage telemetry; set before importing deepeval

import anthropic  # noqa: E402
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams


class ClaudeJudge(DeepEvalBaseLLM):
    """Lets DeepEval use a Claude model (reads ANTHROPIC_API_KEY, model from JUDGE_MODEL)."""

    def __init__(self):
        self.model_name = os.getenv("JUDGE_MODEL", "claude-haiku-5-5")
        self.client = anthropic.Anthropic()
        self.aclient = anthropic.AsyncAnthropic()
        super().__init__(self.model_name)

    def load_model(self):
        return self.client

    @staticmethod
    def _finish(text: str, schema):
        if schema is None:
            return text
        m = re.search(r"\{.*\}", text, re.S)
        return schema(**json.loads(m.group(0) if m else text))

    @staticmethod
    def _text(resp) -> str:
        return "".join(b.text for b in resp.content if b.type == "text")

    def _kwargs(self, prompt: str, schema):
        if schema is not None:
            prompt += "\n\nReply with a single JSON object only, no other text."
        return dict(model=self.model_name, max_tokens=2000, messages=[{"role": "user", "content": prompt}])

    def generate(self, prompt: str, schema=None):
        resp = self.client.messages.create(**self._kwargs(prompt, schema))
        return self._finish(self._text(resp), schema)

    async def a_generate(self, prompt: str, schema=None):
        resp = await self.aclient.messages.create(**self._kwargs(prompt, schema))
        return self._finish(self._text(resp), schema)

    def get_model_name(self) -> str:
        return self.model_name


def _chunks(reference: str) -> list[str]:
    """Split the source text into paragraph-sized pieces for DeepEval's retrieval_context."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", reference) if p.strip()]
    return parts or [reference]


class DeepEvalEvaluator:
    def __init__(self, thresholds: dict):
        self.judge = ClaudeJudge()
        self.t = thresholds

    def evaluate(self, question: str, ground_truth: str, answer: str,
                 answerable: str = "yes", reference: str = "") -> dict:
        """Returns {metric: score, metric_reason: text}; faithfulness is None when not applicable."""
        case = LLMTestCase(
            input=question, actual_output=answer, expected_output=ground_truth,
            retrieval_context=_chunks(reference) if reference else None,
        )
        metrics = {
            "de_answer_relevancy": AnswerRelevancyMetric(
                threshold=self.t["answer_relevancy"], model=self.judge, async_mode=False),
            "de_correctness": GEval(
                name="Correctness", model=self.judge, async_mode=False, threshold=self.t["correctness"],
                criteria="Does the actual output convey the same facts as the expected output "
                         "(or the same behaviour, if the expected output describes behaviour such as declining)?",
                evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT,
                                   SingleTurnParams.EXPECTED_OUTPUT]),
        }
        if answerable == "yes" and reference and reference != "(no source available)":
            metrics["de_faithfulness"] = FaithfulnessMetric(
                threshold=self.t["faithfulness"], model=self.judge, async_mode=False)

        out = {"de_answer_relevancy": None, "de_correctness": None, "de_faithfulness": None}
        reasons = []
        for name, metric in metrics.items():
            metric.measure(case)
            out[name] = round(float(metric.score), 3)
            if metric.reason:
                reasons.append(f"{name[3:]}: {metric.reason}")
        out["de_reason"] = " | ".join(reasons)
        return out

    def check(self, scores: dict) -> list[str]:
        fails = []
        for key, thr in (("de_answer_relevancy", "answer_relevancy"), ("de_correctness", "correctness"),
                         ("de_faithfulness", "faithfulness")):
            if scores.get(key) is not None and scores[key] < self.t[thr]:
                fails.append(f"deepeval {key[3:]} {scores[key]} < {self.t[thr]}")
        return fails
