#!/usr/bin/env sh
set -e
if [ -z "$JWT_SECRET" ]; then
  echo "[FATAL] JWT_SECRET is not set. Aborting." >&2
  exit 64
fi
if [ -f /app/wait-for.sh ]; then
  sh /app/wait-for.sh || true
fi
echo "[OK] Environment looks good. Starting..."
exec "$@"
