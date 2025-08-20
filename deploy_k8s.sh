#!/usr/bin/env bash
set -euo pipefail
echo "Building Docker images locally..."
docker build -t ai-agent-frontend:latest -f frontend/Dockerfile.prod frontend
docker build -t ai-agent-core:latest -f services/agent-core/Dockerfile.prod services/agent-core
docker build -t ai-agent-retrieval:latest -f services/retrieval/Dockerfile.prod services/retrieval
docker build -t ai-agent-ledger:latest -f services/ledger-service/Dockerfile.prod services/ledger-service
echo "Applying Kubernetes manifests..."
kubectl apply -f k8s/agent-core-deployment.yaml || true
echo "Done"
