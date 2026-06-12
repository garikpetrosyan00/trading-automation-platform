# Reconciliation Worker Compose Runbook

This runbook starts the standalone Binance Testnet delayed-reconciliation worker as an explicit, separate Docker Compose service. Normal `docker-compose up` still starts only the default application services.

## Prerequisites

- Database migrations are applied through `20260613_0028`.
- PostgreSQL is available to the Compose project.
- The API is available when you want to inspect worker heartbeat status from HTTP.
- Binance Testnet configuration is prepared only when intentionally testing remote reconciliation.
- `BINANCE_TESTNET_RECONCILIATION_WORKER_ENABLED` remains `false` by default.

Do not put live Binance credentials in this local testnet workflow.

## Preview Services

Default Compose services should not include the worker:

```bash
docker-compose config --services
```

Expected default services:

```text
postgres
api
```

Preview the explicit worker overlay:

```bash
docker-compose \
  -f docker-compose.yml \
  -f docker-compose.reconciliation-worker.yml \
  config --services
```

The overlay output should include:

```text
execution-reconciliation-worker
```

Validate the merged configuration without printing environment values:

```bash
docker-compose \
  -f docker-compose.yml \
  -f docker-compose.reconciliation-worker.yml \
  config >/dev/null
```

## Start Explicitly

The worker has a double opt-in:

- include `docker-compose.reconciliation-worker.yml`
- pass `BINANCE_TESTNET_RECONCILIATION_WORKER_ENABLED=true`

Start only the worker service:

```bash
BINANCE_TESTNET_RECONCILIATION_WORKER_ENABLED=true \
docker-compose \
  -f docker-compose.yml \
  -f docker-compose.reconciliation-worker.yml \
  up -d execution-reconciliation-worker
```

The service runs:

```text
python -m app.cli.run_execution_reconciliation_worker
```

It processes at most one due reconciliation job per poll cycle. There is no FastAPI startup hook, scheduler, daemon registration, or default worker auto-start path.

## View Safe Logs

```bash
docker-compose \
  -f docker-compose.yml \
  -f docker-compose.reconciliation-worker.yml \
  logs --tail=100 execution-reconciliation-worker
```

The worker logs safe lifecycle result codes and internal IDs only. Do not add secrets, signed query strings, headers, or raw Binance payloads to logs.

## Inspect Status

With the API running:

```bash
curl -s http://127.0.0.1:8000/api/v1/execution-reconciliation-worker/status | python -m json.tool
```

Interpretation notes:

- `configured_enabled=false` is a valid non-error state.
- `initialized=false` means the worker has never started and is a valid non-error state.
- `state="running"` alone does not prove liveness.
- Use `last_heartbeat_at`, `heartbeat_stale_after_seconds`, and `is_stale` to judge heartbeat freshness.
- `is_stale=true` means the latest persisted heartbeat is older than the configured threshold.

## Stop Only The Worker

```bash
docker-compose \
  -f docker-compose.yml \
  -f docker-compose.reconciliation-worker.yml \
  stop execution-reconciliation-worker
```

Remove only the worker container:

```bash
docker-compose \
  -f docker-compose.yml \
  -f docker-compose.reconciliation-worker.yml \
  rm -f execution-reconciliation-worker
```

After shutdown, inspect status again:

```bash
curl -s http://127.0.0.1:8000/api/v1/execution-reconciliation-worker/status | python -m json.tool
```

Depending on how the container stopped, the persisted state may show `stopped` or a stale heartbeat. Treat heartbeat freshness as the operator signal.
