#!/bin/sh
set -eu
if [ -n "${UNO_SOUND_STORAGE_DIR:-}" ]; then
  case "$UNO_SOUND_STORAGE_DIR" in /*) ;; *) exit 1 ;; esac
  install -d -o runner -g runner -m 0750 "$UNO_SOUND_STORAGE_DIR"
  install -d -o runner -g runner -m 0750 "$UNO_SOUND_STORAGE_DIR/audio"
fi
# Only the isolated staging pilot enables this storage. Never migrate or reset another service.
if [ "${GAMEOPS_ROUNDS_ENABLED:-0}" = "1" ]; then
  test "${GAMEOPS_ENVIRONMENT:-}" = "staging"
  test "${UNO_SPIN_DB_PATH:-}" = "/data/uno-luck/game.sqlite3"
  install -d -o runner -g runner -m 0750 /data/uno-luck
fi
exec runuser -u runner -- uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
