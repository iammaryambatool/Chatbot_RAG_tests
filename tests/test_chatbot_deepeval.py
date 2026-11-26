"""Second, independent evaluation of the same chatbot answers using the DeepEval library.

Run alone:  .venv\Scripts\python.exe -m pytest tests/test_chatbot_deepeval.py
"""
from src.metrics import load_reference


def test_chatbot_answer_deepeval(case, get_reply, deepeval_evaluator, record_deepeval):
    reply = get_reply(case["question"])
    answerable = case.get("answerable", "yes")
    if not reply.text.strip():
        scores = {"de_answer_relevancy": 0.0, "de_correctness": 0.0, "de_faithfulness": None,
                  "de_reason": "Empty / no reply from chatbot"}
    else:
        scores = deepeval_evaluator.evaluate(
            case["question"], case["ground_truth"], reply.text,
            answerable=answerable, reference=load_reference(case.get("expected_source", "")))
    fails = deepeval_evaluator.check(scores)
    if reply.timed_out:
        fails.append("bot reply timed out")

    record_deepeval({
        "id": case["id"], "category": case.get("category", ""), "question": case["question"],
        "answerable": answerable, "answer": reply.text, **scores,
        "passed": int(not fails), "failures": "; ".join(fails),
    })
    assert not fails, f"[{case['id']}] {'; '.join(fails)} | {scores['de_reason']}"
