# Text-to-Instructor

> Turn the training page open in your browser into an engaging, spoken mini-lecture — with the diagrams shown in sync.

**Status:** `v0.1.0` · **Alpha** (first working release) · macOS · Apple Silicon

Text-to-Instructor is a local, privacy-friendly learning companion for people who
retain more by **listening and looking** than by silently reading. It reads the
page you already have open in Chrome (e.g. Cisco U / u.cisco.com), writes an
instructor-style walkthrough of the concept, narrates it in a natural local voice,
and shows each **diagram right as it's discussed** — so you stay engaged instead of
skimming text next to a static picture.

Built for self-paced, diagram-heavy technical study — networking, security, and
certification prep (CCNA/CCNP and similar) — and helpful for anyone who finds plain
text-to-speech too monotonous to focus on.

### Features
- 📖 Reads the **live page in your Chrome** (keeps your login) — no copy/paste
- 🗣️ **Natural local voice** (Kokoro neural TTS) — not robotic system TTS
- 🖼️ **Diagrams auto-advance in sync** with the narration
- 🧠 **Swappable brain:** your Claude subscription, your OpenAI subscription, the Claude API, or fully-local Ollama
- 🔒 **Local-first:** captured content stays on your machine (fully offline with Ollama)
- ⏯️ Player controls: play/pause (spacebar), prev/next, speed, auto-advance toggle

## How it works

`Narrate this page` → capture the active Chrome tab (text + diagrams via the
DevTools Protocol) → a vision LLM writes an ordered narration tagged to each
diagram → Kokoro renders natural speech locally → the player plays the audio and
auto-advances the diagrams.

## Prerequisites

- **Python 3.12**
- **Google Chrome**
- **Kokoro voice model** (local TTS): download `kokoro-v1.0.onnx` and
  `voices-v1.0.bin` from
  [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases)
  and drop both into `models/`.
- One brain (the thing that writes the narration). Pick any:
  - **Claude subscription** (`LLM_PROVIDER=claude_code`, recommended): the
    [Claude Code](https://claude.com/claude-code) CLI, logged into your plan.
    No API key, strong diagram vision.
  - **OpenAI subscription** (`LLM_PROVIDER=codex`): the Codex CLI logged into
    your OpenAI/ChatGPT plan. No API key, attaches diagrams directly (fast).
  - **Claude API** (`LLM_PROVIDER=claude`): set `ANTHROPIC_API_KEY` in `.env`.
  - **Ollama** (`LLM_PROVIDER=ollama`, fully local): install
    [Ollama](https://ollama.com); a vision model (`llama3.2-vision`) reads the
    diagrams, or a text model (e.g. `qwen3`) narrates from the diagram captions.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env   # then fill in ANTHROPIC_API_KEY (or set LLM_PROVIDER=ollama)
# put kokoro-v1.0.onnx and voices-v1.0.bin into models/
```

> Note: this app attaches to *your* Chrome over CDP, so you do **not** need to run
> `playwright install` — no separate browser is downloaded.

## Use it

1. **Launch Chrome with debugging on** (one-time habit — a normal Chrome window
   won't expose the debugging port):
   ```bash
   bash scripts/launch-chrome.sh
   ```
   Log into u.cisco.com in that window and open a lesson page.
2. **Start the app:**
   ```bash
   t2i
   ```
   The player opens at http://127.0.0.1:8765.
3. Click **▶ Narrate this page**. The first run loads the voice model (a few
   seconds); after that it's quick. Spacebar = play/pause.

## Configuration (`.env`)

| Variable | Meaning |
|---|---|
| `LLM_PROVIDER` | `claude_code`, `codex`, `claude`, or `ollama` |
| `CLAUDE_BIN` / `CLAUDE_CODE_MODEL` | claude CLI path / model (subscription brain) |
| `CODEX_BIN` / `CODEX_MODEL` | codex CLI path / model (subscription brain) |
| `ANTHROPIC_API_KEY` | required only for `LLM_PROVIDER=claude` (API) |
| `CLAUDE_MODEL` | API model (default `claude-opus-4-8`) |
| `OLLAMA_MODEL` | local model, e.g. `llama3.2-vision` or `qwen3:8b` |
| `OLLAMA_HOST` | where Ollama runs, e.g. `http://192.168.1.50:11434` |
| `TTS_VOICE` / `TTS_SPEED` | Kokoro voice and speaking rate |
| `CDP_URL` | Chrome debugging endpoint (default `http://localhost:9222`) |
| `HOST` / `PORT` | local player server |

## Troubleshooting

- **"Couldn't reach Chrome's debugging port"** — start Chrome via
  `scripts/launch-chrome.sh` (the port is only open when Chrome is launched with
  `--remote-debugging-port`).
- **"Kokoro model files are missing"** — put both model files in `models/`.
- **No diagrams narrated** — the page may use tiny/lazy images; only images above
  a minimum size are treated as diagrams.

## Roadmap (post-alpha)

- YouTube course narration (transcript-based)
- Hands-free auto-narrate on page change
- Cross-platform (Windows/Linux) browser launch
- One-click desktop packaging

## Disclaimer

This is a personal study and accessibility aid. Captured page content (text and
diagram screenshots) stays on your machine and is sent to a model only to write the
narration — pick the **Ollama** brain to keep everything fully local. Respect the
terms of service and copyright of any site you use it with; this repository ships
no third-party content.

## Keywords

networking · Cisco · CCNA · CCNP · security · study aid · accessibility · focus ·
text-to-speech · TTS · Kokoro · narration · e-learning · audio learning ·
local-first · FastAPI · Playwright · Chrome DevTools Protocol · Claude · OpenAI ·
Ollama

## License

[MIT](LICENSE)
