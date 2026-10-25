#!/bin/sh
set -eu
# This launcher is only selected by deploy/Dockerfile.dev02.
[ "${UNO_SPIN_DB_PATH:-}" = "/tmp/uno-dev02/database/uno_luck.sqlite3" ] || { echo 'DEV02 database scope missing'; exit 1; }
[ "${UNO_SOUND_STORAGE_DIR:-}" = "/tmp/uno-dev02/sound" ] || { echo 'DEV02 sound scope missing'; exit 1; }
install -d -o runner -g runner -m 0750 /tmp/uno-dev02 /tmp/uno-dev02/database /tmp/uno-dev02/sound
# All source requests are GET. The copied catalog is private to this instance,
# and a reviewed hash prevents a later source edit from silently changing it.
# Render free QA endpoints may cold-start with a temporary 502. Try the
# pinned DEV01 source first, then the primary read-only published source only
# if it matches the exact same SHA-256. No Sound Cloud publishes or imports.
saved_origin="${UNO_DEV02_SOUND_SOURCE:-}"
capture_ok=0
for origin in "$saved_origin" "https://uno-luck-render-staging.onrender.com"; do
  [ -n "$origin" ] || continue
  export UNO_DEV02_SOUND_SOURCE="$origin"
  attempt=1
  while [ "$attempt" -le 3 ]; do
    if runuser -u runner -- python -m app.dev02_sound_snapshot; then
      capture_ok=1
      break
    fi
    echo "[DEV02 SOUND] Read-only pinned snapshot unavailable from $origin (attempt $attempt)" >&2
    attempt=$((attempt+1))
    sleep 3
  done
  [ "$capture_ok" -eq 0 ] || break
done
[ "$capture_ok" -eq 1 ] || { echo "[DEV02 SOUND] No matching published sound snapshot; deployment blocked" >&2; exit 1; }
exec runuser -u runner -- python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
