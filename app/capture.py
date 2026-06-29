"""Capture the active Chrome tab over the DevTools Protocol.

Connects to a Chrome that was started with --remote-debugging-port (see
scripts/launch-chrome.sh), finds the tab you're actually looking at, and pulls
its readable text plus its diagrams as element screenshots (so they come out
correct even when the page is behind a login).
"""

from __future__ import annotations

import trafilatura
from playwright.async_api import Page, async_playwright

from app.config import DIAGRAMS_DIR, settings
from app.models import Diagram, PageCapture

# Ignore tiny images (icons, spacers, logos); keep real diagrams.
MIN_W, MIN_H = 180, 110
MAX_DIAGRAMS = 25

# Per-image, in the browser: pull alt text and nearby caption/heading for context.
_CONTEXT_JS = """
(img) => {
  const alt = img.getAttribute('alt') || '';
  let context = '';
  const fig = img.closest('figure');
  if (fig) {
    const cap = fig.querySelector('figcaption');
    if (cap) context = cap.innerText.trim();
  }
  if (!context) {
    let el = img;
    for (let i = 0; i < 6 && el; i++) {
      el = el.previousElementSibling || el.parentElement;
      if (el && /^H[1-6]$/.test(el.tagName)) { context = el.innerText.trim(); break; }
    }
  }
  return { alt, context };
}
"""


def _is_player_url(url: str) -> bool:
    """True for the app's own player page, so we never narrate the control panel."""
    port = settings.port
    return any(
        url.startswith(f"http://{host}:{port}")
        for host in (settings.host, "127.0.0.1", "localhost")
    )


async def _pick_active_page(pages: list[Page]) -> Page | None:
    """Choose the visible http(s) tab; fall back to the last http(s) page.

    The app's own player tab is skipped, so capturing always targets the lesson
    page even if the player happens to be the foreground tab.
    """
    fallback: Page | None = None
    for p in pages:
        if not p.url.startswith("http") or _is_player_url(p.url):
            continue
        fallback = p
        try:
            if await p.evaluate("document.visibilityState === 'visible'"):
                return p
        except Exception:
            continue
    return fallback


async def _extract_diagrams(page: Page) -> list[Diagram]:
    diagrams: list[Diagram] = []
    handles = await page.query_selector_all("img")
    for handle in handles:
        if len(diagrams) >= MAX_DIAGRAMS:
            break
        try:
            box = await handle.bounding_box()
            if not box or box["width"] < MIN_W or box["height"] < MIN_H:
                continue
            await handle.scroll_into_view_if_needed(timeout=2000)
            idx = len(diagrams)
            png_name = f"diagram-{idx}.png"
            await handle.screenshot(path=str(DIAGRAMS_DIR / png_name))
            meta = await handle.evaluate(_CONTEXT_JS)
            diagrams.append(
                Diagram(
                    idx=idx,
                    png_path=png_name,
                    alt=meta.get("alt", ""),
                    context=meta.get("context", ""),
                )
            )
        except Exception:
            continue  # skip images that won't screenshot (lazy/offscreen/etc.)
    return diagrams


async def capture_active_tab() -> PageCapture:
    """Attach to the running Chrome and capture whatever tab is in front."""
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(settings.cdp_url)
        except Exception as e:
            raise ConnectionError(
                "Couldn't reach Chrome's debugging port. Start Chrome with "
                "scripts/launch-chrome.sh, then log in and open your lesson page."
            ) from e

        try:
            pages = [p for ctx in browser.contexts for p in ctx.pages]
            page = await _pick_active_page(pages)
            if page is None:
                raise ConnectionError("No open web page found in Chrome to narrate.")

            title = await page.title()
            html = await page.content()
            text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
            diagrams = await _extract_diagrams(page)

            return PageCapture(url=page.url, title=title, text=text, diagrams=diagrams)
        finally:
            # Detach without closing the user's real browser.
            await browser.close()
