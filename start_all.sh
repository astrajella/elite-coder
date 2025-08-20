#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "Starting ledger-service..."
python "$ROOT/services/ledger-service/main.py" &
sleep 1
echo "Starting retrieval..."
python "$ROOT/services/retrieval/main.py" &
sleep 1
echo "Starting agent-core..."
python "$ROOT/services/agent-core/main.py" &
sleep 1
echo "Starting frontend (Next.js)... (you need to run npm install first)"
cd "$ROOT/frontend"
npm run dev &
sleep 1
echo "All services started (logs in terminal). Visit http://localhost:3000"
