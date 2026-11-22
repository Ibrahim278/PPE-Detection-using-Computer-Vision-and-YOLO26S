#!/bin/sh
# Starts the API on $PORT (Render and most hosts set it; default 8000).
# When started as root (the default), make sure the data volume is writable by the
# unprivileged "app" user (fresh cloud disks are often root-owned), then drop privileges.
set -eu

PORT="${PORT:-8000}"
DATA="${PPE_STORAGE_DIR:-/data}"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA" /tmp/ultralytics
    chown app:app "$DATA" /tmp/ultralytics
    # Only fix ownership below the top level if it's actually wrong (cheap on large volumes).
    if [ -n "$(find "$DATA" -mindepth 1 ! -user app -print -quit 2>/dev/null)" ]; then
        chown -R app:app "$DATA"
    fi
    exec setpriv --reuid=app --regid=app --init-groups --inh-caps=-all \
        uvicorn app.main:app --app-dir /app/api --host 0.0.0.0 --port "$PORT" \
        --workers 1 --proxy-headers --forwarded-allow-ips '*' "$@"
fi

exec uvicorn app.main:app --app-dir /app/api --host 0.0.0.0 --port "$PORT" \
    --workers 1 --proxy-headers --forwarded-allow-ips '*' "$@"
