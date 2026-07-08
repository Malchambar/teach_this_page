# CLAUDE.md — Teach This Page (Python / Chrome-CDP reference app)

## What this is
A local voice app that turns any open web page into a spoken, image-synced
lesson. It attaches to your **already-logged-in Chrome over the DevTools
Protocol (CDP)**, extracts the page's readable text + each diagram, has an LLM
describe the diagrams and write a narration, then speaks it locally with Kokoro
TTS while auto-advancing the images. Subject-agnostic (Wikipedia, iFixit,
WikiHow, Cisco U, etc.); originally inspired by Cisco U courses.

**This is the known-good reference implementation.** The Electron ("own
browser") port is a separate project at `../teach_this_page-app` — see
[docs/electron-kickoff.md](docs/electron-kickoff.md). Keep this app working; the
Electron app is judged by "does it match this."

## Stack
- **Python ≥ 3.12**, packaged with hatchling (`pyproject.toml`, single manifest —
  no requirements.txt, no Node here).
- **FastAPI + uvicorn** backend; **Playwright** attaches to Chrome over CDP
  (does NOT download a browser — no `playwright install` needed).
- **trafilatura** for readable-text extraction; **Pillow** for photo-vs-diagram.
- **kokoro-onnx + soundfile** for local neural TTS.
- LLM SDKs: **anthropic**, **openai**, **ollama**.
- Frontend: dependency-free vanilla HTML/JS/CSS in `app/static/` (zero build).

## Run it
```bash
source venv/bin/activate           # venv is named `venv` (not .venv)
bash scripts/launch-chrome.sh      # opens debug Chrome on port 9222 w/ dedicated profile
                                   # → log into your site in THAT window
t2i                                # console entry (app.main:run); player at http://127.0.0.1:8765
```
Two processes: the debug Chrome (leave running, log in there) and `t2i`.
The `DevTools listening on ws://127.0.0.1:9222/...` line = Chrome launched OK;
the rest of Chrome's/GoogleUpdater's stderr is harmless noise.

## Setup (fresh machine)
1. `python3.12 -m venv venv && source venv/bin/activate && pip install -e .`
   (`-e` = editable install; edits to `app/` take effect with no reinstall.)
2. `cp .env.example .env` and set providers (see below).
3. Download `kokoro-v1.0.onnx` + `voices-v1.0.bin` from
   github.com/thewh1teagle/kokoro-onnx/releases into `models/`.
4. Install the CLIs for the default engines: `brew install --cask claude-code`
   (the CLI cask — NOT `claude`, which is the desktop app) + `claude` login;
   `brew install codex` + `codex login`. Or use Ollama / an API key instead.

## Engines (the "brains")
Two roles, set in `.env`: `VISION_PROVIDER` (reads diagrams) and
`WRITER_PROVIDER` (writes narration). Options: `claude_code`, `codex`, `claude`
(API), `gemini`/`grok`/`openrouter` (API), `ollama` (local), `off` (vision only).
Dispatched by `app/llm/__init__.py::get_provider()`. Default pair is
`claude_code` (vision) + `codex` (writer) — no API key, uses the subscription
CLIs shelled out via `app/proc.py`.

**Model-var gotcha:** each engine reads its OWN model variable. `CLAUDE_CODE_MODEL`
drives the `claude` CLI (NOT `CLAUDE_MODEL`, which is only for the `claude` API
engine); `CODEX_MODEL` drives the `codex` CLI. Leave a CLI model blank to use
whatever that CLI is configured for. Current `.env` uses the cheapest tiers
(`haiku`, `gpt-5.4-mini`).

## Architecture / flow
`POST /api/narrate` → `pipeline.build_lesson()`:
1. `capture.capture_active_tab()` — reads active Chrome tab over CDP; text via
   trafilatura, each diagram as an element screenshot (works behind logins).
2. vision engine describes diagrams (cached by image content).
3. writer engine turns text + descriptions into ordered narration segments,
   tagging which diagram to show per segment.
4. Kokoro renders speech locally + lazily (segment 1 plays while rest render).
5. Player auto-advances diagrams; pauses at Cisco "Content Review Question"s.

## Key files
- `app/main.py` — FastAPI app + all routes + `run()` entry point.
- `app/pipeline.py` — `build_lesson()` orchestrator.
- `app/capture.py` — largest file; CDP extraction + the JS snippets (`_LOAD_JS`,
  `_CONTEXT_JS`, `_STEPS_JS`, `_SCROLL_JS`, `_JUNK_SELECTOR`) + `_hires_src` /
  `_fetch_image_bytes` (per-CDN image upscaling, iFixit/WikiHow).
- `app/models.py` — Pydantic contract: `PageCapture`, `Step`, `Diagram`,
  `Segment`, `Lesson`, `LessonStats`.
- `app/config.py` — settings/env, storage dirs, `purge_generated()`.
- `app/tts.py` — Kokoro synthesis (`models/` paths + `_SPEAK_FIXES` respellings).
- `app/llm/` — engine implementations (`base`, `vision`, `chat`, `claude`,
  `claude_code`, `codex`, `ollama`, `openai_compat`).
- `app/static/` — the vanilla player UI (`index.html`, `player.js`, `chat.js`).
- `scripts/launch-chrome.sh` — launches debug Chrome (port 9222, `.chrome-profile`).

## Conventions & gotchas
- **Privacy / no-retention is a product value.** `data/diagrams`, `data/audio`,
  `data/descriptions` are purged on shutdown (`config.purge_generated()` via the
  FastAPI `lifespan`). `preferences.json` is kept; chat history is client-side.
  Don't add retention. `/api/diagrams.zip` exists but its UI trigger is
  deliberately disabled (copyright).
- Match the surrounding style: terse comments explaining *why*, not *what*.
- Chrome path is hardcoded (`/Applications/Google Chrome.app/...`), overridable
  via `CHROME_APP`; CDP endpoint via `CDP_URL` (default `http://localhost:9222`).
- **Known limitation:** CDP capture can't reach SCORM/iframe corporate LMS pages
  (the Palo Alto case) and can trip single-session guards — that's the entire
  reason the Electron port exists. Don't try to fix it here.
- License: PolyForm Noncommercial 1.0.0.

## Docs
- `docs/synopsis.md` — product positioning (subject-agnostic learning companion).
- `docs/electron-kickoff.md` — handoff for the Electron port.
- `docs/commercialization.md` — strategy + ToS/legal risk map (not a committed
  plan; never market as a course-ripper).
