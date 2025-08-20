#!/usr/bin/env sh
set -e
if [ -z "${JWT_SECRET:-}" ]; then
  echo "[FATAL] JWT_SECRET missing; refusing to start" >&2
  exit 42
fi
exec "$@"
