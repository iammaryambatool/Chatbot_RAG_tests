# Chatbot LLM Test Framework (Appium + pytest + Claude judge)

Flow: start emulator + Appium -> launch app (from `capabilities.json`) -> replay the **recorded flow**
to the chatbot -> for each CSV row ask the question -> score the reply vs ground truth -> CSV/JSON report.

## One-time setup

```
cd chatbot-rag-tests
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env         # put your ANTHROPIC_API_KEY in .env
```

You don't need to activate the venv. Call `.venv\Scripts\python.exe` directly, which also works when
PowerShell blocks `Activate.ps1` under a Group Policy. Prerequisites: Android SDK (emulator + `adb`),
Node.js with Appium and the UiAutomator2 driver.

`.env` is git-ignored. `JUDGE_MODEL` sets the Claude model used as judge.

## Step 1 - capabilities (`config/capabilities.json`)

Edit this one file; the framework starts the emulator and Appium for you.

- `emulator.avd_name`: `Pixel_7` or `Medium_Phone_API_36.1` (`emulator -list-avds`)
- `capabilities."appium:appPackage"`: your app's package. Find it with
  `python -m src.list_apps` (user-installed apps) or `python -m src.list_apps chat` (search).
- App not installed yet? Drag the APK onto the emulator, or add `"appium:app": "path/to/app.apk"`.
- The app is force-restarted on every run (`forceAppLaunch`) so the recorded flow always starts at the same place.

## Step 2 - record the flow

```
python -m src.recorder
```

1. The app opens in the emulator. **Tap through to the chatbot yourself** (mouse in the emulator window,
   ~2 s between taps, no keyboard). Each tap is printed. `undo` removes the last step. Enter when on the chat screen.
2. Calibration: send one message and wait for the reply, then type that message in the terminal.
   The recorder figures out the input box, send button and bot-bubble locators.
3. Saved to `flows/chatbot_flow.json` (+ screen dumps in `flows/debug/` for troubleshooting).
   If it prints `NOT FOUND` or a WARNING (common with bubbles that have no resource-id), edit
   `flows/chatbot_flow.json` by hand. `python -m src.inspect_screen` lists the elements on the current screen.

Re-record any time the app's navigation changes. Keep the emulator in portrait.

## Step 3 - test data

Edit `data/test_cases.csv`. Columns: `id, category, question, ground_truth, expected_source, answerable`.

- `expected_source`: key of the page the answer comes from (see [sources.md](sources.md)). The judge reads
  `sources/<key>.txt` to check faithfulness. Those files are git-ignored, so recreate them from the URLs
  in `sources.md` after cloning. An empty key means the judge sees all sources.
- `answerable`: `yes`, or `no` for questions the knowledge base doesn't cover (out of scope, personal data,
  medical advice, prompt injection). For `no` rows the bot should decline or redirect, not invent an answer.

## Step 4 - run

```
.venv\Scripts\python.exe -m pytest
```

Results: `reports/results_<time>.csv` (every answer + scores) and `reports/summary_<time>.json`.

## Metrics

| Metric       | Scale   | How                                 |
| ------------ | ------- | ----------------------------------- |
| correctness  | 1-5     | Claude judge vs ground truth        |
| relevance    | 1-5     | Claude judge                        |
| faithfulness | 1-5     | Claude judge vs source text (5 = no hallucination) |
| similarity   | 0-1     | Claude judge (semantic closeness)   |
| latency_s    | seconds | send -> reply complete              |

Thresholds live in `config/config.yaml` under `evaluation.thresholds`.

## DeepEval (second, independent evaluation)

`tests/test_chatbot_deepeval.py` re-scores the same bot answers with the [DeepEval](https://github.com/confident-ai/deepeval)
library, using Claude as the judge (`src/deepeval_metrics.py`). Each question is only asked to the bot once,
and the reply is shared with the main test.

| Metric (0-1)         | How                                                      |
| -------------------- | -------------------------------------------------------- |
| `de_answer_relevancy` | DeepEval `AnswerRelevancyMetric`                         |
| `de_correctness`      | DeepEval `GEval` vs ground truth                         |
| `de_faithfulness`     | DeepEval `FaithfulnessMetric` vs source text (`answerable = yes` rows only) |

```
.venv\Scripts\python.exe -m pytest tests/test_chatbot_deepeval.py   # DeepEval only
.venv\Scripts\python.exe -m pytest tests/test_chatbot.py            # original judge only
```

Thresholds: `config/config.yaml` under `deepeval.thresholds`. Output: `reports/deepeval_results_<time>.csv`
and `reports/deepeval_summary_<time>.json`. DeepEval telemetry is turned off.

## Project layout

| Path | Purpose |
| ---- | ------- |
| `config/` | `capabilities.json` (emulator/app), `config.yaml` (locators, thresholds) |
| `flows/chatbot_flow.json` | recorded navigation + chatbot locators |
| `data/test_cases.csv` | questions, ground truth, source key, answerable flag |
| `sources/` | local text of the knowledge-base pages (git-ignored) |
| `src/` | driver, recorder, navigator, chatbot page object, judge (`metrics.py`), DeepEval (`deepeval_metrics.py`) |
| `tests/` | pytest suite |
| `reports/` | generated results (git-ignored) |
