// Player: requests a narrated lesson, then plays each segment's audio while
// showing its diagram, auto-advancing to the next.

const $ = (id) => document.getElementById(id);

const els = {
  narrate: $("narrate"),
  voice: $("voice"),
  speed: $("speed"),
  provider: $("provider"),
  status: $("status"),
  stage: $("stage"),
  diagram: $("diagram"),
  caption: $("caption"),
  transcript: $("transcript"),
  player: $("player"),
  prev: $("prev"),
  next: $("next"),
  playpause: $("playpause"),
  segCounter: $("seg-counter"),
  audio: $("audio"),
  autoadvance: $("autoadvance"),
};

let lesson = null;
let cur = 0;

// Always return a finite, positive playback rate (the dropdown can be blank).
function currentSpeed() {
  const v = parseFloat(els.speed.value);
  return Number.isFinite(v) && v > 0 ? v : 1.0;
}

// Select the dropdown option matching a numeric speed, else default to 1.0x.
function applySpeedDefault(v) {
  const match = [...els.speed.options].find((o) => parseFloat(o.value) === parseFloat(v));
  els.speed.value = match ? match.value : "1.0";
}

function setStatus(msg, isError = false) {
  els.status.textContent = msg || "";
  els.status.classList.toggle("error", isError);
}

async function narrate() {
  els.narrate.disabled = true;
  els.stage.classList.add("hidden");
  els.player.classList.add("hidden");
  setStatus("Reading the page in Chrome, writing the lecture, and generating audio… this can take a moment.");

  try {
    const res = await fetch("/api/narrate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        voice: els.voice.value,
        speed: parseFloat(els.speed.value),
        provider: els.provider.value || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);

    lesson = data;
    if (!lesson.segments || lesson.segments.length === 0) {
      throw new Error("No narration was produced for this page.");
    }
    setStatus(`${lesson.title || lesson.url} — ${lesson.segments.length} segments`);
    cur = 0;
    els.stage.classList.remove("hidden");
    els.player.classList.remove("hidden");
    loadSegment(0, true);
  } catch (e) {
    setStatus(e.message, true);
  } finally {
    els.narrate.disabled = false;
  }
}

function diagramFor(seg) {
  if (seg.image_idx === null || seg.image_idx === undefined) return null;
  return (lesson.diagrams || []).find((d) => d.idx === seg.image_idx) || null;
}

function loadSegment(i, autoplay) {
  if (!lesson || i < 0 || i >= lesson.segments.length) return;
  cur = i;
  const seg = lesson.segments[i];

  const dia = diagramFor(seg);
  if (dia) {
    els.diagram.src = `/diagrams/${dia.png_path}`;
    els.caption.textContent = dia.alt || dia.context || "";
    els.diagram.classList.remove("hidden");
  } else {
    els.diagram.classList.add("hidden");
    els.caption.textContent = "";
  }

  els.transcript.textContent = seg.speak;
  els.segCounter.textContent = `${i + 1} / ${lesson.segments.length}`;

  els.audio.src = `/audio/${seg.audio_path}`;
  els.audio.playbackRate = currentSpeed();
  if (autoplay) els.audio.play().catch(() => {});
}

function togglePlay() {
  if (els.audio.paused) els.audio.play().catch(() => {});
  else els.audio.pause();
}

els.audio.addEventListener("ended", () => {
  // Only roll into the next segment when auto-advance is on.
  if (els.autoadvance.checked && cur < lesson.segments.length - 1) {
    loadSegment(cur + 1, true);
  }
});
els.audio.addEventListener("play", () => (els.playpause.textContent = "⏸"));
els.audio.addEventListener("pause", () => (els.playpause.textContent = "▶"));

els.narrate.addEventListener("click", narrate);
els.playpause.addEventListener("click", togglePlay);
els.prev.addEventListener("click", () => loadSegment(cur - 1, true));
els.next.addEventListener("click", () => loadSegment(cur + 1, true));
els.speed.addEventListener("change", () => {
  els.audio.playbackRate = currentSpeed();
});

// Spacebar = play/pause when a lesson is loaded.
document.addEventListener("keydown", (e) => {
  if (e.code === "Space" && lesson && e.target.tagName !== "SELECT") {
    e.preventDefault();
    togglePlay();
  }
});

// Pull defaults from the server settings.
fetch("/api/settings")
  .then((r) => r.json())
  .then((s) => {
    if (s.tts_voice) els.voice.value = s.tts_voice;
    if (s.tts_speed) applySpeedDefault(s.tts_speed);
  })
  .catch(() => {});
