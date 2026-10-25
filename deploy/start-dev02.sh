#!/bin/sh
set -eu
# This launcher is only selected by deploy/Dockerfile.dev02.
[ "${UNO_SPIN_DB_PATH:-}" = "/tmp/uno-dev02/database/uno_luck.sqlite3" ] || { echo 'DEV02 database scope missing'; exit 1; }
[ "${UNO_SOUND_STORAGE_DIR:-}" = "/tmp/uno-dev02/sound" ] || { echo 'DEV02 sound scope missing'; exit 1; }
install -d -o runner -g runner -m 0750 /tmp/uno-dev02 /tmp/uno-dev02/database /tmp/uno-dev02/sound
# All source requests are GET. The copied catalog is private to this instance,
# and a reviewed hash prevents a later source edit from silently changing it.
runuser -u runner -- python -m app.dev02_sound_snapshot
exec runuser -u runner -- python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
