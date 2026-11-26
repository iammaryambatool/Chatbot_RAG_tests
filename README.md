# Chatbot LLM Test Framework (Appium + pytest + Claude judge)

Flow: start emulator + Appium -> launch app (from `capabilities.json`) -> replay the **recorded flow**
to the chatbot -> for each CSV row ask the question -> score the reply vs ground truth -> CSV/JSON report.

## One-time setup

```
cd C:\Users\maryambatool\chatbot-llm-tests
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env         # put your ANTHROPIC_API_KEY in .env
```

## Step 1 - capabilities (`config/capabilities.json`)

Edit this one file; the framework starts the emulator and Appium for you.

- `emulator.avd_name`: `Pixel_7` or `Medium_Phone_API_36.1` (`emulator -list-avds`)
- `capabilities."appium:appPackage"`: your app's package. Find it with
  `python -m src.list_apps` (user-installed apps) or `python -m src.list_apps chat` (search).
- App not installed yet? Drag the APK onto the emulator, or add `"appium:app": "C:\\path\\app.apk"`.
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

Edit `data/test_cases.csv` (columns: id, category, question, ground_truth).

## Step 4 - run

```
pytest
```

Results: `reports/results_<time>.csv` (every answer + scores) and `reports/summary_<time>.json`.

## Metrics

| Metric       | Scale   | How                                 |
| ------------ | ------- | ----------------------------------- |
| correctness  | 1-5     | Claude judge vs ground truth        |
| relevance    | 1-5     | Claude judge                        |
| faithfulness | 1-5     | Claude judge (5 = no hallucination) |
| similarity   | 0-1     | Claude judge (semantic closeness)   |
| latency_s    | seconds | send -> reply complete              |

Thresholds live in `config/config.yaml` under `evaluation.thresholds`.
