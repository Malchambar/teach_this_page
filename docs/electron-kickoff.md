# Electron Version — Kickoff Handoff

**Written:** 2026-07-01, at the end of the engine-hardening phase on `main`.
**Purpose:** everything a fresh session needs to start building the standalone
Electron ("self-contained browser") version of Teach This Page. Read this file,
[synopsis.md](synopsis.md) (what the product is), and the roadmap plan at
`~/.claude/plans/wiggly-scribbling-corbato.md` (the full options analysis) —
then start. Strategy planning is **done**; what remains before code is only the
*implementation* plan for the Electron POC itself (step 1 below).

---

## 1. Where we are right now

### `main` is the known-good product — keep it that way
`main` (pushed, clean at `7f054aa`) is the working local Python app: FastAPI on
127.0.0.1:8765, zero-build static player in `app/static/`, capture of the active
Chrome tab over CDP (port 9222), pluggable vision/writer LLM engines, local
Kokoro TTS. The deliberate strategy this phase (user's call): **harden the
Python engine first, so the Electron port is "does it match Python," not "figure
out what it should do."** That hardening is now in good shape.

Electron work happens on a **branch** (`productization` exists and is parked on
GitHub — reuse it or branch fresh, e.g. `electron`, off `main`). `main` stays
the reference implementation the Electron app must match.

### Proven behavior (tested on real, diverse sites)
- **Wikipedia, every subject** — art (Kintsugi, Watercolor), food (Sourdough),
  finance/real-estate (Escrow), mythology. Image-rich and text-only both work.
- **iFixit Step Mode** — multi-step guides (up to 48 steps), per-step image
  slideshows, jump-to-step anchors, hi-res image upgrade (.standard → .large).
- **WikiHow** — steps + images; inline 460px thumbs auto-upgrade to 728px.
- **Martha Stewart (Dotdash)** — freeform article; after the recirc fix it
  captured exactly the article's 3 own photos (was 19 with junk), vision cost
  $0.10 → $0.00, whole lesson ≈ $0.04 API-equivalent.
- **Cisco U (logged-in course)** — the original use case; works.
- **Codex/Claude/etc. engines** — per-pass token/cost stats with a realistic
  "≈ if API" estimate; codex reports its real model (e.g. gpt-5.4-mini).

### This session's engine fixes (all on `main`, all verified live)
- `c127688` — synopsis broadened beyond tech (subject-agnostic positioning).
- `24c3a90` — WikiHow hi-res images: `-<N>px-` URL token bumped to ≥728px, with
  fallback to the original URL if the upgrade 404s (`_fetch_image_bytes`).
- `ab5c217` — **recirc exclusion**: skip images inside `aside/footer/nav` or
  containers whose class/id matches related/recommend/newsletter/taboola/etc.
  Applied to BOTH freeform paths (live-DOM via `img.closest()` in `_LOAD_JS`;
  server-HTML via lxml ancestor walk `_in_junk_container`). Big cost win.
- `34de0c9` + `7f054aa` — TTS says "econ" as EE-kon (`_SPEAK_FIXES` respelling,
  audio-only) + cache version bump so it applies.

---

## 2. Why Electron, and the case that motivates it

Full analysis in the roadmap plan (Path E). Short version: ship the app as its
own browser (Electron = bundled Chromium + Node, like VS Code/Cursor). The user
logs in *inside* the app (pass-through auth — the app never touches
credentials), browses to any page, clicks Teach This Page.

**The motivating failure (reproduced this session):** Palo Alto's LMS
(learn.paloaltonetworks.com). Its lessons are **SCORM content in an embedded
iframe**, and it enforces single-session — our CDP capture read the *course
syllabus shell* instead of the lesson, and the act of activating the tab via CDP
tripped its "second window" guard and **expired the user's session** (debug
capture literally contained "Session expired… Please log in again"). In
Electron, the app owns the embedded page: no CDP, no tab-juggling, no second
window to detect, and iframes are reachable. This class of page (corporate LMS,
SCORM players) is *unreachable* from the current architecture — don't try to
fix it in Python; it's the Electron demo case.

---

## 3. Target architecture (agreed direction)

- **Electron shell** = the product window: an embedded browser (webContents /
  WebContentsView) the user browses and logs in with, plus the player UI.
- **Python backend stays, as a bundled sidecar** — no rewrite. Everything from
  `main` is reused: pipeline, LLM engines, TTS, pricing/stats, player.
  It keeps serving `/api/*` on localhost.
- **Capture flips direction**: instead of the backend *pulling* the page over
  CDP, the shell *pushes* page data in. The extraction logic is **already
  JavaScript** inside `app/capture.py` — `_LOAD_JS` (lazy-load + junk skip),
  `_CONTEXT_JS` (captions/video detection), `_STEPS_JS` + `_SCROLL_JS` (step
  pages), `_JUNK_SELECTOR` — designed to be runnable via
  `webContents.executeJavaScript` unchanged. New backend endpoint (e.g.
  `POST /api/capture`) accepts the pushed capture (text, image URLs or bytes,
  steps, video flags); the Python `PageCapture`/`Step`/`Diagram` models in
  `app/models.py` are the contract.
- **Images**: the shell fetches them inside its authenticated session (same
  origin as the page) and pushes bytes; `_hires_src` logic ports trivially (it's
  pure URL string munging).
- **Player UI** (`app/static/`) is vanilla JS/HTML/CSS, zero build — render it
  in the shell as a second view/tab, unchanged, still talking to `/api/*`.

### Sequencing (from the roadmap; step 1 of the recommended order is folded in)
1. **POC first**: thin Electron shell — embedded browser + a "Teach This Page"
   button that runs the extraction JS, POSTs to the existing Python server
   (launched manually, as today), and opens the existing player. Success = a
   lesson builds end-to-end with **zero CDP** — then try Palo Alto.
2. Then: bundle Python as a real sidecar (spawn/manage from Electron;
   PyInstaller or bundled venv), first-run onboarding (choose engine, paste
   key), OS-agnostic paths.
3. Later: installer/signing, auto-update, and (separate tier) the hosted
   service + recommendations layer.

---

## 4. What the next session should do

1. Confirm branch strategy (reuse `productization` vs new `electron` branch —
   either is fine; keep `main` untouched).
2. **Plan mode**: write the concrete POC implementation plan — Electron app
   layout, how the extraction JS is shared with `capture.py` without forking it
   (extract to `app/static/extract/` or a shared JS file both read), the
   `POST /api/capture` schema (mirror `PageCapture`), image-byte transport,
   iframe handling for SCORM.
3. Build the POC; verify on: a Wikipedia page, WikiHow (steps), and then the
   Palo Alto lesson (the case CDP can't do).

## 5. Key files (the port surface)

- `app/capture.py` — all extraction logic; the JS snippets to lift are
  `_LOAD_JS`, `_CONTEXT_JS`, `_STEPS_JS`, `_SCROLL_JS`, `_JUNK_SELECTOR`,
  plus `_hires_src` / `_fetch_image_bytes` (Python, port or expose via API).
- `app/models.py` — `PageCapture`/`Step`/`Diagram`/`Segment`/`Lesson`/
  `LessonStats`: the data contract the new capture endpoint must produce.
- `app/pipeline.py` — `build_lesson()`; today it calls `capture_active_tab()`;
  the Electron path needs a variant that accepts a pushed `PageCapture`.
- `app/main.py` — FastAPI routes; add `POST /api/capture` (or narrate-with-
  payload); `/api/debug` is the inspection tool — keep it working.
- `app/static/` — the whole player; reuse as-is.
- `app/llm/*`, `app/tts.py`, `app/pricing.py` — untouched by the port.

## 6. Parked / open items (not blockers)

- **`docs/commercialization.md`** — strategy + ToS/legal risk map distilled
  from the user's "OpenClaw" threads; user may paste more threads to fold in.
  Key operational takeaways: privacy/no-retention/BYO-engine is the *moat*;
  accessibility + enterprise-wiki are the low-risk beachheads; never market as
  a course-ripper; hosted (Path C) changes the legal posture.
- WikiHow lesson title captured as "Progressive" instead of the article title —
  cosmetic; prefer `document.title`/`og:title`. Fix whenever convenient.
- Hi-res upgrades are per-CDN (iFixit + WikiHow done); add others only if a
  real site shows painfully small article images.
- Offered but not built: a "this looks like a course shell / expired session,
  not the lesson" warning when a capture is text-thin + 0 diagrams + reads like
  an error page. Superseded somewhat by Electron (which fixes the cause), but
  still a nice guard for the CDP path.
- Anti-bot sites (Investopedia, AllRecipes) can't be tested from headless
  harnesses — they work in the user's real logged-in Chrome; test there.
