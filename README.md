# Euchre Pilot

AI agent that plays Euchre 3D on Android via screen reading, with game recording and LLM-powered analysis.

## Architecture

Two connected systems that feed each other:

**System 1 — The Player:** Watches Euchre 3D via ADB screenshots, reads game state through template matching, makes decisions via a rule-based strategy engine, and executes actions by tapping the screen.

**System 2 — The Recorder + Analyst:** Logs every hand in full (cards held, decisions made, trick outcomes, scores) to SQLite. An LLM analyst reviews hands and finds patterns across games. Findings feed back into improving the player's decision rules.

## Setup

```bash
# Install
pip install -e ".[dev]"

# Run simulated games (no device needed)
euchre-simulate -n 100

# Start the dashboard
euchre-dashboard

# Calibrate screen reader (requires Android device with Euchre 3D)
euchre-calibrate

# Run live play agent
euchre-play
```

## Modules

```
src/euchre_pilot/
  engine/        Core game logic — cards, rules, state, game loop
  player/        Decision-making — rule-based strategy, random baseline
  vision/        Screen reading — ADB capture, template matching
  calibration/   One-time setup — LLM labels screenshots to build template library
  android/       Device automation — ADB wrapper, tap/swipe controller
  recorder/      Data layer — SQLite storage, event logging
  analyst/       LLM analysis — hand evaluation, pattern finding
  dashboard/     Local web UI — FastAPI server for viewing results
  cli.py         Command-line entry points
```

## How Calibration Works

1. Connect Android device via ADB
2. Run `euchre-calibrate` while Euchre 3D plays AI-vs-AI games
3. Screenshots are captured and sent to a vision LLM (Claude by default)
4. The LLM identifies every card and UI element with bounding boxes
5. Regions are cropped, labeled, and saved as template images
6. After enough games (~10), all 24 cards are covered
7. Template library is complete — no LLM needed at runtime

## Stack

- Python 3.11+
- OpenCV — screenshot processing, template matching
- Pydantic + instructor — structured LLM responses
- Anthropic SDK — LLM API (provider-agnostic via instructor)
- SQLite — game data storage
- FastAPI + Jinja2 — local dashboard

## Commands

| Command | Description |
|---------|-------------|
| `euchre-simulate` | Run engine-only games between AI players |
| `euchre-calibrate` | Build template library from Euchre 3D screenshots |
| `euchre-play` | Run live agent against Euchre 3D |
| `euchre-analyze` | LLM analysis of recorded games |
| `euchre-dashboard` | Start local web dashboard (default: localhost:8420) |
