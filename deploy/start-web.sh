#!/bin/sh
set -eu

# At this point the container starts as root solely to prepare an attached
# persistent volume. The server itself always runs as UID 10001, never root.
if [ -n "${UNO_SOUND_STORAGE_DIR:-}" ]; then
  case "$UNO_SOUND_STORAGE_DIR" in
    /*) ;;
    *) echo "[UNO SOUND] Storage path must be absolute" >&2; exit 1 ;;
  esac

  # The existing mount can be root:root and mode 0755; a Dockerfile RUN chown
  # does not help because the Railway mount is attached AFTER the image build.
  install -d -o runner -g runner -m 0750 "$UNO_SOUND_STORAGE_DIR"
  install -d -o runner -g runner -m 0750 "$UNO_SOUND_STORAGE_DIR/audio"
  # Existing files are preserved. Only the two top-level directories are
  # claimed; no recursive delete, chmod, copy, or database operations.
  echo "[UNO SOUND] Persistent volume directories prepared"
fi

# Render's persistent disk starts root-owned too. Prepare only the explicitly
# configured database directory; do not move/reset an existing database.
# With this variable unset the existing Railway behavior is unchanged.
if [ -n "${UNO_SPIN_DB_PATH:-}" ]; then
  case "$UNO_SPIN_DB_PATH" in
    /*) ;;
    *) echo "[UNO DB] Database path must be absolute" >&2; exit 1 ;;
  esac
  db_dir=$(dirname -- "$UNO_SPIN_DB_PATH")
  case "$db_dir" in
    /|/tmp|/app) echo "[UNO DB] Use a dedicated database directory" >&2; exit 1 ;;
  esac
  install -d -o runner -g runner -m 0750 "$db_dir"
  echo "[UNO DB] Persistent database directory prepared"
fi

# Drop privileges before reading any app data or serving public traffic.
exec runuser -u runner -- uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
