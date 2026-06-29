"""FastAPI app: serves the local player UI and the narrate pipeline endpoint."""

from __future__ import annotations

import subprocess
import sys
import webbrowser
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import __version__
from app.config import AUDIO_DIR, DIAGRAMS_DIR, settings

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Text-to-Instructor", version=__version__)

# Player assets, plus captured diagrams and generated audio, served straight off disk.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/diagrams", StaticFiles(directory=DIAGRAMS_DIR), name="diagrams")
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": __version__}


@app.get("/api/settings")
def get_settings() -> dict:
    """Non-secret settings the UI shows (never returns the API key)."""
    return {
        "llm_provider": settings.llm_provider,
        "claude_model": settings.claude_model,
        "ollama_model": settings.ollama_model,
        "ollama_host": settings.ollama_host,
        "tts_voice": settings.tts_voice,
        "tts_speed": settings.tts_speed,
        "cdp_url": settings.cdp_url,
    }


class NarrateRequest(BaseModel):
    voice: str | None = None
    speed: float | None = None
    provider: str | None = None


@app.post("/api/narrate")
async def narrate(req: NarrateRequest) -> dict:
    """Capture the active Chrome tab, build the lecture, return it for playback."""
    from app.pipeline import build_lesson  # lazy import keeps server boot cheap

    try:
        lesson = await build_lesson(
            voice=req.voice,
            speed=req.speed,
            provider=req.provider,
        )
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:  # surface a readable message to the UI
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}") from e
    return lesson.model_dump()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def _open_player(url: str) -> None:
    """Open the player as a tab in the debugging Chrome profile.

    Targets the same --user-data-dir launch-chrome.sh uses, so the player lands
    in the already-running instructing window — not the default browser (Safari)
    and not your personal Chrome profile.
    """
    if sys.platform == "darwin" and Path(settings.chrome_app).exists():
        try:
            subprocess.Popen(
                [settings.chrome_app, f"--user-data-dir={settings.chrome_profile_dir}", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # detach so it can't block the server
            )
            return
        except Exception:
            pass
    webbrowser.open(url)  # last resort: default browser


def run() -> None:
    """Console entry point (`t2i`): start the server and open the player."""
    import uvicorn

    url = f"http://{settings.host}:{settings.port}/"
    _open_player(url)
    print(f"Text-to-Instructor running at {url}")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    run()
