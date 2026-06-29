# Text-to-Instructor

> Turn the training page open in your browser into an engaging, spoken mini-lecture — with the diagrams shown in sync.

**Status:** `v0.2.0` · **Alpha** · macOS · Apple Silicon

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
- 🗣️ **Natural local voice** (Kokoro neural TTS) — not robotic system TTS — switchable mid-lesson
- 🖼️ **Diagrams auto-advance in sync** with the narration
- 🧠 **Split engines:** mix a **vision** engine (reads diagrams) and a **writer** engine (narrates) — e.g. Claude for diagrams + Codex for text — using your Claude/OpenAI subscriptions, the Claude API, or fully-local Ollama
- ⏸️ **Knows when to stop:** detects Cisco "Content Review Question" sections and pauses so you can answer
- ⚡ **Lazy audio:** playback starts as soon as the first segment is ready; the rest render in the background
- 🔒 **Local-first:** captured content stays on your machine (fully offline with Ollama)
- ⏯️ Player controls: play/pause (spacebar), prev/next, speed (live), auto-advance toggle

## How it works

`Narrate this page` →
1. **Capture** the active Chrome tab over the DevTools Protocol — the readable text
   plus each diagram as an element screenshot (works behind your login).
2. **Vision** engine describes each diagram (cached by image, so re-runs are fast).
3. **Writer** engine turns the page text + diagram descriptions into an ordered
   narration, tagging which diagram to show with each part.
4. **Kokoro** renders natural speech locally, **lazily** — segment 1 plays within a
   second while the rest render in the background.
5. The **player** plays the audio and auto-advances the matching diagram, stopping
   at content-review questions.

(If the vision and writer engines are the same, steps 2–3 collapse into one pass.)

## Prerequisites

- **Python 3.12**
- **Google Chrome**
- **Kokoro voice model** (local TTS): download `kokoro-v1.0.onnx` and
  `voices-v1.0.bin` from
  [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases)
  and drop both into `models/`.
- **At least one engine** (see the table below).

## Engines & account requirements

The narration is produced by two roles — a **vision** engine (reads diagrams) and
a **writer** engine (writes the narration). You can use the same engine for both,
or mix them. Each role can be any of:

| Engine | What it needs | Free account? | Setup |
|---|---|---|---|
| **`claude_code`** | **Claude Pro or Max** (or an Anthropic API key with credit) | ❌ No | Install [Claude Code](https://claude.com/claude-code), run `claude` once and log in |
| **`codex`** | **ChatGPT Plus or higher** (or an OpenAI API key with credit) | ❌ No | `brew install codex`, then `codex login` |
| **`claude`** (API) | An **Anthropic API key** with credit (pay per use) | n/a | Put `ANTHROPIC_API_KEY` in `.env` |
| **`ollama`** | A capable local machine (a vision model is ~5–8 GB) | ✅ **Yes — free & local** | Install [Ollama](https://ollama.com); `ollama pull llama3.2-vision` |
| **`off`** (vision only) | — | ✅ Yes | No vision engine; narrates from Cisco's built-in alt-text |

> **Free vs. paid, in short:** the `claude_code` and `codex` engines require a
> *paid* Claude/ChatGPT subscription — a free account on either will not work. If
> you have neither, use **Ollama** (fully free and local) or **API keys**
> (pay-as-you-go, no subscription). The default config uses `claude_code` for
> vision and `codex` for writing; change `VISION_PROVIDER` / `WRITER_PROVIDER` in
> `.env` (or the dropdowns in the player) to match what you have.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env   # then set VISION_PROVIDER / WRITER_PROVIDER to engines you have
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
   seconds); after that it's quick.

### In the player
- **Vision** / **Writer** dropdowns — pick the engine for each role (or leave at the
  `.env` defaults).
- **Voice** — switch any time, even mid-lesson; it re-records from where you are.
- **Speed** — live; changes playback instantly.
- **Auto-advance** — on, it rolls into the next segment automatically; off, it stops
  after each so you advance with ⏭.
- **Spacebar** — play/pause. **⏮ / ⏭** — previous / next segment.
- **Content review questions** — playback stops and shows a banner; answer it in
  Cisco, then press ⏭ to continue.

## Configuration (`.env`)

| Variable | Meaning |
|---|---|
| `VISION_PROVIDER` | engine that reads diagrams: `claude_code`, `codex`, `claude`, `ollama`, or `off` |
| `WRITER_PROVIDER` | engine that writes narration (same options) |
| `LLM_PROVIDER` | fallback writer if `WRITER_PROVIDER` is unset |
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

## Changelog

### v0.2.0
- **Split engines** — independent **Vision** (reads diagrams) and **Writer**
  (narrates) engines, selectable per run. Same engine for both = one combined pass;
  `VISION_PROVIDER=off` = narrate from Cisco alt-text only.
- **Cached diagram descriptions** — the vision pass is cached by image content and
  runs concurrently, so re-narrating/re-voicing a page is much faster.
- **Lazy audio** — playback starts as soon as the first segment is voiced; the rest
  render in the background (with prefetch), instead of waiting for the whole page.
- **Live voice switching** — change the voice mid-lesson and it re-records from the
  current segment and resumes.
- **Content Review Question handling** — detected, announced, and the player pauses
  instead of auto-advancing past it.
- **Full-page narration** — raised the page text limit (16k → 120k chars) so long
  lessons are narrated end to end.
- **Speed fixes** — playback speed is now live and applied once (was doubled), and
  the Speed control no longer throws on a blank value.
- **Player opens in the debugging Chrome profile** (not Safari or your personal
  Chrome), and capture ignores the player's own tab.

### v0.1.0
- First working release: capture the page in Chrome, narrate it with diagrams in
  sync, local Kokoro voice, swappable brain (Claude / Codex / Claude API / Ollama).

## License

[MIT](LICENSE)
