#!/usr/bin/env sh
set -e

if [ -z "$JWT_SECRET" ]; then
  echo "ERROR: JWT_SECRET is required but not set" >&2
  exit 1
fi

# Optional: allow disabling auth for local-only dev
if [ "$ALLOW_INSECURE" = "true" ]; then
  echo "WARNING: ALLOW_INSECURE=true; JWT checks may be bypassed in development." >&2
fi

exec "$@"
