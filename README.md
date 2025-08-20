# AI Code-Agent — Next Grade Upgrade (Phase-2 scaffold)

This archive contains your uploaded project plus a Phase-2 scaffold for production-grade upgrades:

- services/agent-core (FastAPI) - tool invocation scaffold
- services/retrieval (FastAPI) - retrieval API stub
- services/ledger-service (FastAPI) - ledger + stats + daily export
- frontend/ (Next.js) - minimal scaffold to migrate the UI
- providers/ - adapter stubs for OpenAI / Anthropic
- docker-compose.yml - to run local containers (builds from service folders)
- k8s/ - basic Kubernetes manifest examples
- .github/workflows/ci.yml - basic CI workflow

## How to run (local)
1. Ensure Python 3.11 and Node.js installed.
2. From repo root, start services (example using uvicorn):
   - python services/agent-core/main.py (or run via uvicorn)
   - python services/retrieval/main.py
   - python services/ledger-service/main.py
3. Start the Next.js frontend:
   - cd frontend && npm install && npm run dev
4. The frontend should proxy or call the services on ports 8001/8002/8003 as configured in GATEWAY_README.md.

## Phase-2 next steps (recommended)
- Implement provider adapters with real API keys & streaming support.
- Integrate a vector DB (pgvector/Milvus/Weaviate).
- Implement PEFT/LoRA fine-tuning pipelines and connect to `fine_tune.py`.
- Harden security (OAuth, RBAC), add autoscaling and monitoring, and integrate CI/CD pipelines.


## Phase-2 Step 1 Completed — Provider adapters & Next.js + microservices scaffold

- Provider adapters for OpenAI, Anthropic, OpenRouter (respect ALLOW_INTERNET env var).
- Retrieval service can optionally use pgvector (stub) or local sentence-transformers fallback.
- Agent-core includes a simple JWT secret-based auth (JWT_SECRET env) and logs runs to ledger-service.
- Next.js frontend scaffold with dashboard and editor pages (proxy via next.config.js).

To run locally (development):
1. Start ledger: `python services/ledger-service/main.py`
2. Start retrieval: `python services/retrieval/main.py`
3. Start agent-core: `python services/agent-core/main.py`
4. Start frontend: `cd frontend && npm install && npm run dev`

Note: Some packages (sentence-transformers) are heavy and may require additional system deps when installing.


## Phase-2 Step 3 Completed

- Added pgvector migration SQL and seed script (services/retrieval/migrations).
- Implemented JWT-based auth and RBAC in agent-core with register/login endpoints.
- Added apply_migrations.py convenience script to apply migrations to Postgres.
- Migrated frontend with pages: dashboard (Recharts), monaco (Monaco editor), editor (streaming), and auth flow stub.
- CI updated to smoke test ledger service in CI.

Next: integrate full Monaco diff editor (side-by-side), wire editor's commit/apply flows to agent-core, and implement PEFT fine-tune runner hooks.


## Phase-2 Step 6 Completed

- Ledger service can now use PostgreSQL when `LEDGER_DB_URL` is set. Migration SQL available at `services/ledger-service/migrations/001_create_ledger.sql`.
- Agent-core exposes artifact listing and download endpoints; frontend artifacts page lists and allows downloads.
- Playwright E2E workflow added: `.github/workflows/e2e.yml` to run end-to-end tests in CI.

To enable Postgres locally, set `LEDGER_DB_URL` or `PG_CONN` to your Postgres connection string and run `apply_migrations.py`.


## Phase-2 Step 8 Completed

- Agent-core now supports Postgres-backed user store via `AGENT_USER_DB_URL` (fallback to SQLite).
- Password reset flow: `/auth/request_reset` returns a reset token (email sending is stubbed); `/auth/reset` sets new password.
- Metrics endpoints: `/metrics` on agent-core and ledger-service expose simple Prometheus-style counters.
- Services now initialize basic logging. k8s manifests updated with readiness probe against `/metrics`.


## Phase-2 Step 9 Completed

- SMTP email helper (`utils/email_helper.py`) used by `/auth/request_reset` to optionally send reset emails when SMTP_ env vars are provided.
- GitHub OAuth2 stub endpoints added: `/auth/github/start` and `/auth/github/callback` (requires `GITHUB_CLIENT_ID/SECRET` for real use).
- Ledger service now prefers Postgres when `LEDGER_DB_URL` is set and uses connection pooling with retries.
- Observability: Prometheus scrape config at `observability/prometheus_scrape.yml` and a sample Grafana dashboard JSON at `observability/grafana_dashboard.json`.
- Fine-tune runner (`fine_tune.py`) can optionally orchestrate HF trainer when `USE_HF_TRAINING=true` (stub: heavy deps not bundled).

Next recommended steps: enable real HF training in a GPU-enabled environment, wire GitHub OAuth client credentials, and configure SMTP provider for production email sends.


## Production deployment (overview)

This project includes production-ready Dockerfiles and a sample docker-compose.prod.yml to run the system behind nginx.

Steps:
1. Build and push images via GitHub Actions (configure GHCR_PAT secret) or build locally with `docker build`.
2. Use `docker-compose -f docker-compose.prod.yml up -d` to start the stack.
3. Or use `deploy_k8s.sh` to build images and apply Kubernetes manifests (requires kubectl).

Notes:
- Configure environment variables (`.env`) for API keys, database URLs, SMTP, and secrets.
- For TLS, put a reverse proxy in front with certs (not included).


## Phase-2 Step 11 Completed

- Frontend migrated to Next.js App Router (app/ directory) with SSR-compatible pages and a server-side login route that sets HTTP-only cookie `ai_token`.
- Pages: /, /dashboard, /editor, /monaco, /artifacts, /login.


Phase-2 Step 12b: Hardened proxy & CSRF complete. Server-side proxy route available at `/api/proxy` to safely forward authenticated requests from the frontend to the agent-core after validating JWT via `/auth/validate`. CSRF tokens must be requested from `/auth/csrf` and sent in `x-csrf-token` for state-changing operations.


## PgVector backend for RAG

This release adds a `PgVectorStore` backend using Postgres + pgvector. To use:

1. Install dependencies: `pip install psycopg2-binary pgvector`
2. Set `PG_CONN` env var to your Postgres connection string.
3. Run migrations: `python apply_pg_migrations.py` (requires PG_CONN)
4. Index docs: `python services/retrieval/build_index_pg.py`
5. Set `RAG_BACKEND=pgvector` and start services.

Notes: pgvector extension must be enabled on your Postgres instance. The vector dimension defaults to 384 (all-MiniLM-L6-v2).


## RAG Demo Page

A simple RAG demo page is available at `/rag` in the frontend. It posts to the retrieval API endpoint (configured via `NEXT_PUBLIC_RETRIEVAL_URL` or `/api/retrieval/search`). Use the Top K / Hops / Expansion K controls to experiment with multi-hop retrieval.


## Orchestrator service

A new `services/orchestrator` service coordinates persona tool calls and records runs. Start it with `python services/orchestrator/main.py` or via Docker Compose (port 8010). The frontend includes an Orchestrator Playground at `/orchestrator`.


## Orchestrator visualizations

The Orchestrator Playground now includes Recharts-based visualizations for per-step timing and per-persona cost breakdown. To enable charts, install Recharts in the frontend:

```bash
cd frontend
npm install recharts
```

If Recharts is not installed the UI will gracefully show raw JSON data instead.


## Orchestrator security and retry settings

Environment variables introduced:
- ORCH_API_KEY: API key required on incoming orchestrator requests (header `x-orch-api-key` or Authorization Bearer). If empty, API key enforcement is disabled.
- ORCH_SERVICE_TOKEN: token used by orchestrator when calling downstream services (sent as `Authorization: Bearer <token>`).
- ORCH_RETRY_MAX: max retry attempts per step (default 3).
- ORCH_RETRY_BACKOFF: backoff multiplier base seconds for retry exponential backoff (default 2.0).

These changes implement per-step retries, idempotency-key forwarding to agent-core, resume and cancel endpoints, and schema validation enforcement via agent-core `tool_validate_schema` when `expected_schema` is provided in a plan step.


### Orchestrator worker pool & metrics
- **ORCH_WORKERS**: number of concurrent worker coroutines processing runs (default 2).
- Run submission enqueues work; workers execute in the background. See `/metrics` for Prometheus-style counters.
- Streaming tool calls: orchestrator now parses SSE/JSONL to aggregate exact tokens and cost per chunk when providers stream.


## Orchestrator Metrics & Tracing Enrichment

### Prometheus Metrics
The orchestrator now exposes rich, labeled Prometheus metrics at `/metrics`:

- `orch_tool_calls_total{persona,tool,status}`
- `orch_tool_tokens_total{persona,tool}`
- `orch_tool_cost_total{persona,tool}`
- `orch_tool_call_seconds_bucket{persona,tool,...}` (Histogram)
- Sliding-window percentile gauges (computed in-memory):  
  - `orch_tool_latency_p50_seconds{persona,tool}`  
  - `orch_tool_latency_p95_seconds{persona,tool}`  
  - `orch_tool_latency_p99_seconds{persona,tool}`

Configure window size via `ORCH_METRICS_WINDOW` (default: 500).

### OpenTelemetry Tracing
Tool calls are wrapped in spans: `tool:<name>` with attributes (`persona`, `tool`, `expected_schema`, `stream`).  
Configure OTLP HTTP export with:

```
export OTEL_SERVICE_NAME=orchestrator
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces
```

If not set, spans are emitted to the console exporter.

### Requirements
Added to `requirements.txt`:
- `prometheus_client`
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp`
- `opentelemetry-instrumentation-fastapi`


## Durable Queue & Fair Scheduling

- **SQLite durable queue** (`ORCH_QUEUE_DB` path, default: `/tmp/orchestrator_queue.db`).
- Crash-safe: queued/running/done/failed persisted with timestamps and attempts.
- **Fair scheduling**: priority + FIFO; per-project locks prevent interleaving steps from the same project.
- **Admin & Health**:
  - `GET /healthz` – liveness
  - `GET /readyz` – readiness + queue stats
  - `POST /admin/drain/start` – enable draining (stop accepting new work)
  - `POST /admin/drain/stop` – disable draining

### Environment
- `ORCH_QUEUE_DB=/path/to/queue.db`

### Run
```
uvicorn services.orchestrator.main:app --port 8002
```


## Fair Scheduling & Crash Recovery

### Fairness (Per-Project Weights)
- New SQLite table `project_weights(project, weight, served_count)`.
- Claiming uses **weighted fairness**: project chosen by minimal `served_count / weight` among queued projects.
- Manage via admin endpoints:
  - `GET /admin/fairness/weights`
  - `POST /admin/fairness/weights` body: `{ "project": "myrepo", "weight": 3 }`

### Heartbeat & Reaper (Crash Recovery)
- Workers heartbeat every 5s while executing a run.
- `ORCH_HEARTBEAT_TIMEOUT` (default **120s**): reaper re-queues stale `running` items.
- Admin endpoint: `POST /admin/reaper/run` to force a sweep.

### Draining
- Workers now **respect drain mode** and stop claiming new work until disabled.

### Tracing
- Parent span `run` created per orchestration with attributes: `run.id`, `project`.
- Tool-call spans continue to be children with persona/tool attributes.


## Graceful Shutdown & Draining
- On process shutdown, orchestrator enters **drain mode**, waits up to `ORCH_DRAIN_TIMEOUT` seconds for in-flight runs to finish, then re-queues any still-running tasks.
- Environment:
  - `ORCH_DRAIN_TIMEOUT=20` (seconds)


## Strict Tool Output Guardrails
- All tool results now flow through a **schema-enforcing shim** (`scheduler.call_tool`).
- Payloads are validated against Pydantic models in `services/orchestrator/schemas.py`:
  - `CodePatchList`, `PlanSchema`, `SummarizerSchema`, `TestResultsSchema`.
- Validation errors trigger **automatic retries** with backoff (`ORCH_MAX_ATTEMPTS`, `ORCH_RETRY_BACKOFF`).

## End-to-End Retry + Resume Test
- `tests/test_e2e_retry_resume.py` injects failures via `ORCH_INJECT_FAIL` to ensure the orchestrator retries and completes.

## Service Auth (API key / JWT)
- Protect sensitive endpoints using either **X-API-Key** or **Bearer JWT (HS256)**.
- Env:
  - `ORCH_API_KEY=...`
  - `ORCH_JWT_SECRET=...` (if set, JWTs must be HS256-signed; include `exp` in payload)


## Idempotent Step Execution
- New table **run_steps** tracks `status/attempts/updated_at` per `run_id + step_id`.
- Orchestrator **skips** already finished steps on resume/retry, recorded in Prometheus metric `orch_idempotent_skips_total`.

## Worker Signals
- SIGTERM/SIGINT will flip orchestrator into **drain** mode; shutdown will requeue any still-running tasks.

## Metrics (Prometheus)
- `orch_retries_total{run_id,step_id}`
- `orch_validation_errors_total{tool,schema}`
- `orch_idempotent_skips_total{run_id,step_id}`
- Scrape via `/metrics`.

## New Admin API
- `GET /admin/run_steps/{run_id}` → JSON list of step statuses.


## Retry-aware Queue Leasing
- New **leases** table with TTL and heartbeats. Workers acquire leases per `(run_id, step_id)`; expired leases are removed by `requeue_orphans()`.

## Cross-Process Idempotency Keys
- **executions** table dedupes by `(run_id, step_id, idem_key)`. Scheduler stamps `idem_key = f"{run_id}:{step_id}:{attempts}"` per try.

## OpenTelemetry Tracing
- Spans for **run** and **step** created via `TRACER`. Default exporter: `ConsoleSpanExporter`. Replace with OTLP as needed.

## CSV / NDJSON Exports
- `GET /admin/export/run_steps/{run_id}.ndjson`
- `GET /admin/export/run_steps/{run_id}.csv`


## Watchdog & Orphan Requeue
- Background watchdog runs `requeue_orphans()` every `ORCH_WATCHDOG_SEC` (default 15s).

## OTLP Tracing (optional)
- Set `OTEL_EXPORTER_OTLP_ENDPOINT` to enable OTLP exporter in addition to console exporter.

## Trace IDs in Admin
- `run_steps` now stores `trace_id`. Admin API `/admin/run_steps/{run_id}` returns it (with pagination).

## Bulk CSV Export
- `GET /admin/export/run_steps_all.csv?limit=1000&offset=0`
- `GET /admin/run_steps/{run_id}?limit=200&offset=0`


### Orchestrator UI — Trace IDs & Histograms
- Steps table shows `trace_id` per step and, when `TRACE_BASE` is set (e.g., `https://grafana.example/trace/`), each becomes a clickable link.
- Recharts histograms render from Prometheus `/metrics`:
  - `orch_step_duration_seconds`
  - `orch_lease_wait_seconds`

**Config (frontend):**
- Put your API key in `localStorage.API_KEY`.
- Optional `localStorage.TRACE_BASE` to prefix trace hyperlinks.

### Admin Housekeeping
- `DELETE /admin/runs/{run_id}` — purge a run (steps, leases, executions)
- `POST /admin/compact` — VACUUM SQLite

### Failpoint Injection
- Set `ORCH_FAILPOINT=tool_call:2` to deterministically fail the 2nd tool call for testing retries & resume.


### New: Quantiles, Heatmap & CSV Exports
- Backend now exposes **Summary** metrics alongside Histograms; UI shows p50/p90 cards.
- **Lease contention heatmap** (stacked bars by tool and bucket) via `/admin/metrics/lease_wait_breakdown`.
- **CSV exports**:
  - `/admin/export/histograms.csv`
  - `/admin/export/run_timeline/{run_id}.csv`
- Optional trace drilldown proxy: `/admin/trace/{trace_id}` (set `TRACE_API_BASE`).


### New in this drop
- **p99 cards** for step durations.
- **Sparkline of recent step durations** via `/admin/metrics/durations_series`.
- **Per-persona lease heatmap** and **CSV export** `/admin/export/lease_heat.csv`.
- `lease_wait_samples` now records `persona` when available (defaults to `unknown`).


### New: Trace Inspector
- **Endpoint** `GET /admin/trace/{trace_id}/spans` — derives spans from local `executions` table.
- **CSV export** `GET /admin/export/trace_spans.csv?trace_id=...`.
- **UI** right-drawer trace panel with flame-like visualization + duration bars, plus one-click CSV.
- Works without an external tracing backend; if you set `TRACE_API_BASE`, you can wire a reverse-proxy later.


### New: Critical Path + Tree
- **Endpoint** `GET /admin/trace/{trace_id}/critical_path` — weighted-interval-scheduling to compute a max-duration non-overlapping path.
- **CSV** `GET /admin/export/critical_path.csv?trace_id=...`.
- **UI**: toggle **Only critical path**, flame bars highlight CP spans (amber), plus a **Span Tree** (containment-based).
- **Filters**: global click-to-filter hooks for persona/tool (wire buttons anywhere using `data-filter-persona="..."` or `data-filter-tool="..."`).

> Note: without explicit parent IDs, the tree uses interval containment; CP is the maximum-duration non-overlapping chain, which approximates the bottleneck timeline.


## Added in ctxsearch-refactor build
- **GET /search/code** — developer-facing semantic code search (hybrid/vector modes), persisted via `RAG_VECTOR_DB_PATH`.
- **POST /refactor/preview** and **/refactor/apply** — safe, Pydantic-validated patches with Python syntax checks.
- Frontend: added **Semantic Code Search** and **Refactor** pages with dark UI components.
