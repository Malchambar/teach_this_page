#!/usr/bin/env bash
# Launch Chrome with remote debugging so the app can read the page you're on.
#
# Why: the app attaches to Chrome over the DevTools Protocol (CDP). Chrome only
# exposes that when it's started with --remote-debugging-port. A regular Chrome
# window started from the Dock won't work — start it with this script instead,
# then log into u.cisco.com normally. Login persists in the dedicated profile
# below, so you only sign in once.

set -euo pipefail

PORT="${CDP_PORT:-9222}"
PROFILE_DIR="${CHROME_PROFILE_DIR:-$(cd "$(dirname "$0")/.." && pwd)/.chrome-profile}"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [[ ! -x "$CHROME" ]]; then
  echo "Could not find Google Chrome at: $CHROME" >&2
  echo "Edit scripts/launch-chrome.sh to point CHROME at your Chrome binary." >&2
  exit 1
fi

mkdir -p "$PROFILE_DIR"

echo "Launching Chrome with remote debugging on port $PORT"
echo "Profile: $PROFILE_DIR"
echo "Log into u.cisco.com in this window, then open a lesson page and click 'Narrate this page' in the app."

exec "$CHROME" \
  --remote-debugging-port="$PORT" \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check \
  --disable-features=HighEfficiencyModeAvailable,TabDiscarding,IntensiveWakeUpThrottling \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows \
  --disable-renderer-backgrounding
