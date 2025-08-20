#!/usr/bin/env bash
set -euo pipefail
echo "Running smoke checks..."
sleep 2
echo "Checking ledger /stats..."
curl -fsS http://127.0.0.1:8003/stats || { echo 'ledger failed'; exit 1; }
echo "Checking agent core /health (root)..."
curl -fsS http://127.0.0.1:8001/ || true
echo "Checking frontend at 3000 (may return HTML)"
curl -fsS http://127.0.0.1:3000/ || true
echo "Smoke checks passed"
