from src.metrics import check_thresholds, load_reference


def test_chatbot_answer(case, chatbot, evaluator, cfg, record):
    reply = chatbot.ask(case["question"])
    scores = evaluator.evaluate(case["question"], case["ground_truth"], reply.text, reply.latency_s,
                                answerable=case.get("answerable", "yes"),
                                reference=load_reference(case.get("expected_source", "")))
    fails = check_thresholds(scores, cfg["evaluation"]["thresholds"])
    if reply.timed_out:
        fails.append("bot reply timed out")

    record({
        "id": case["id"], "category": case.get("category", ""),
        "question": case["question"], "expected_source": case.get("expected_source", ""),
        "answerable": case.get("answerable", "yes"), "ground_truth": case["ground_truth"],
        "answer": reply.text, **scores.as_dict(),
        "passed": int(not fails), "failures": "; ".join(fails),
    })

    assert not fails, f"[{case['id']}] {'; '.join(fails)} | reason: {scores.reason}"
