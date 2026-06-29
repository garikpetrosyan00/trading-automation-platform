# Trading Automation Platform

## Project Overview

Trading Automation Platform is a FastAPI backend for strategy configuration, paper-mode execution, local backtesting, and operator-friendly demo workflows. It is designed as a safety-first trading automation foundation: live trading remains disabled by default, paper/backtest paths are isolated, and local demo commands avoid external exchange side effects.

The project currently demonstrates three safe operating surfaces:

- REST APIs for strategies, bots, execution profiles, market data inspection, paper portfolio state, and audit-oriented execution reads.
- Paper/demo tooling for controlled local BUY/SELL smoke verification without live order submission.
- Deterministic CSV backtesting with dataset preparation, saved run artifacts, run comparison, Markdown reporting, and demo bundle export.

Production-grade live trading, production scheduler deployment, authentication, Telegram notifications, and broader broker support are intentionally out of scope for the current demo baseline.

## Portfolio Highlights

- FastAPI backend architecture with routers, services, repositories, schemas, and centralized settings.
- SQLAlchemy 2.x models with Alembic migrations and PostgreSQL-ready configuration.
- Safety-first execution design with explicit paper/testnet/live boundaries and dry-run defaults.
- Deterministic local CSV backtesting that uses only current/past candle data at each step.
- CSV dataset normalization for raw OHLCV inputs, timestamp validation, sorting, dedupe handling, and gap summaries.
- Saved backtest run artifacts: `summary.json`, `trades.csv`, and `equity_curve.csv`.
- Local comparison, Markdown report, and demo bundle export for portfolio/client review.
- Broad pytest coverage for backtest flows, paper execution safety, API behavior, and regression boundaries.

## Safety Guarantees

For the local backtest/demo workflow:

- It is file-based only and runs from CSV artifacts on the local machine.
- It does not fetch Binance or other network market data.
- It does not submit live, testnet, or real exchange orders.
- It does not invoke the bot runner or scheduler loops.
- It does not create runtime paper/live `Order`, `Fill`, `ExecutionAttempt`, `RunEvent`, reconciliation, or database-backed backtest rows.
- It does not add migrations or require database persistence for backtest artifacts.

These guarantees apply to the local CSV backtest demo pipeline and reporting/export helpers. Separate paper-mode and Binance Spot testnet sections below have their own explicit operator checklists.

## Local Backtest Demo Pipeline

The fastest portfolio/demo path is the one-command local pipeline. It prepares a dataset, runs a CSV backtest, optionally compares against a prior run, exports a Markdown report, and packages a clean demo bundle:

```bash
.venv/bin/python -m app.cli.run_backtest_demo_pipeline \
  --symbol BTCUSDT \
  --timeframe 1h \
  --input data/backtests/raw/BTCUSDT_1h_2025.csv \
  --input data/backtests/raw/BTCUSDT_1h_2026.csv \
  --work-dir data/backtests/runs/BTCUSDT_1h_pipeline_demo \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 95000 \
  --exit-above 105000 \
  --order-quantity 0.01 \
  --base-run-dir data/backtests/runs/BTCUSDT_1h_smoke_base \
  --title "BTCUSDT 1h Demo Pipeline"
```

If a prepared CSV already exists, skip dataset preparation:

```bash
.venv/bin/python -m app.cli.run_backtest_demo_pipeline \
  --symbol BTCUSDT \
  --timeframe 1h \
  --prepared-csv data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --work-dir data/backtests/runs/BTCUSDT_1h_pipeline_demo \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 95000 \
  --exit-above 105000 \
  --order-quantity 0.01 \
  --compact
```

Generated structure:

```text
data/backtests/runs/BTCUSDT_1h_pipeline_demo/
├── dataset/
│   ├── prepared.csv
│   └── summary.json
├── run/
│   ├── summary.json
│   ├── trades.csv
│   └── equity_curve.csv
├── comparison.json        # only when comparison input is provided
├── report.md
└── bundle/
    ├── README.md
    ├── manifest.json
    ├── summary.json
    ├── trades.csv
    ├── equity_curve.csv
    ├── comparison.json    # when available
    └── report.md
```

The pipeline refuses a non-empty work directory unless `--overwrite` is passed. Results are historical simulations only; they are not profitability claims and should not be presented as live trading performance.

## Demo Checklist

Use this checklist for a stable local backtest demo checkpoint:

1. Confirm setup assumptions: dependencies are installed in `.venv`, and the command is run from the repository root.
2. Prepare a dataset from raw CSV files under `data/backtests/raw/`, or use an existing prepared CSV under `data/backtests/datasets/`.
3. Run the one-command demo pipeline from [Local Backtest Demo Pipeline](#local-backtest-demo-pipeline).
4. Inspect the generated Markdown report at `<work-dir>/report.md`.
5. Inspect the generated bundle manifest at `<work-dir>/bundle/manifest.json`.

Generated local artifacts under `data/backtests/runs/`, `data/backtests/raw/`, and `data/backtests/datasets/` are ignored by git and should not be committed. Do not commit real private datasets, client data, downloaded exchange history, or local demo bundles unless they have been intentionally sanitized for public presentation.

## Local Backtest Artifact API

Saved local demo artifacts can also be inspected through read-only FastAPI endpoints. These endpoints only read files under `data/backtests/runs/`, reject unsafe artifact names, and return sanitized summary/manifest fields without exposing server filesystem paths.

```bash
curl http://127.0.0.1:8000/api/v1/backtests/local-demo/runs

curl http://127.0.0.1:8000/api/v1/backtests/local-demo/bundles

curl http://127.0.0.1:8000/api/v1/backtests/local-demo/runs/BTCUSDT_1h_pipeline_demo/summary

curl http://127.0.0.1:8000/api/v1/backtests/local-demo/runs/BTCUSDT_1h_pipeline_demo/report

curl http://127.0.0.1:8000/api/v1/backtests/local-demo/bundles/BTCUSDT_1h_demo_bundle/manifest
```

Use the catalog endpoints first when you do not know the generated folder names. They return names, artifact availability, symbol/timeframe when available, and cheap CSV row counts. After choosing a name, read the summary, Markdown report, or bundle manifest with the detail endpoints.

For pipeline outputs, the same summary and manifest reads work with `run/summary.json` and `bundle/manifest.json` inside the pipeline work directory. The API is read-only and file-based: it does not fetch market data, submit orders, invoke the bot runner, persist backtest rows, or create runtime paper/live audit records.

## Local Backtest Parameter Sweep

Use the parameter sweep CLI to compare multiple `price_threshold` parameter combinations against one prepared CSV dataset:

```bash
.venv/bin/python -m app.cli.run_backtest_parameter_sweep \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below-values 90000,95000,100000 \
  --exit-above-values 105000,110000 \
  --order-quantity 0.01 \
  --output-dir data/backtests/runs/BTCUSDT_1h_sweep_demo
```

Generated sweep artifacts:

- `sweep_summary.json`: ranked JSON summary and best result
- `sweep_results.csv`: one row per parameter combination
- `sweep_report.md`: human-readable sweep table
- `run_*/summary.json`, `run_*/trades.csv`, `run_*/equity_curve.csv`: per-combination backtest artifacts

Results are ranked deterministically by final equity with stable tie-breakers. This is local historical simulation only, does not fetch market data or place orders, and is not a profitability guarantee.

Sweep artifacts can also be reviewed through the read-only local-demo API:

```bash
curl http://127.0.0.1:8000/api/v1/backtests/local-demo/sweeps

curl http://127.0.0.1:8000/api/v1/backtests/local-demo/sweeps/BTCUSDT_1h_sweep_demo/summary

curl http://127.0.0.1:8000/api/v1/backtests/local-demo/sweeps/BTCUSDT_1h_sweep_demo/results

curl http://127.0.0.1:8000/api/v1/backtests/local-demo/sweeps/BTCUSDT_1h_sweep_demo/report
```

The sweep API is read-only and local-artifact based. It only reads under `data/backtests/runs/`, rejects unsafe names, does not expose absolute filesystem paths, and does not fetch data, place orders, invoke the bot runner, persist rows, or create runtime paper/live audit records.

## What is included

- FastAPI application entrypoint
- `GET /health` health endpoint
- `GET /api/v1/system/ping` API starter endpoint
- background market-data ingestion for one public symbol stream
- `GET /api/v1/market-data/status` inspection endpoint
- `GET /api/v1/market-data/latest` inspection endpoint
- persisted virtual portfolio account, positions, orders, and fills
- `GET /api/v1/portfolio/summary` portfolio inspection endpoint
- `GET /api/v1/portfolio/positions` open-position inspection endpoint
- `GET /api/v1/execution/orders` simulated order history endpoint
- `GET /api/v1/execution/fills` simulated fill history endpoint
- `POST /api/v1/execution/market-order` simulated market order endpoint
- CRUD endpoints for `Strategy`
- CRUD endpoints for `Bot`
- nested configuration endpoints for `ExecutionProfile`
- nested history endpoints for `BotRun`
- append-only timeline endpoints for `RunEvent`
- Environment-driven settings using Pydantic
- SQLAlchemy 2.x database session and declarative base
- Alembic scaffold with the initial `strategies` migration
- PostgreSQL-ready configuration
- Structured JSON logging
- Centralized exception handling
- Docker and Docker Compose starter files

## Project structure

```text
.
├── alembic/                # Migration environment and future revisions
├── app/
│   ├── api/                # Routers and HTTP endpoints
│   ├── core/               # Settings, logging, error handling
│   ├── data/               # Market data schemas and provider adapters
│   ├── db/                 # SQLAlchemy base and session
│   ├── models/             # ORM models
│   ├── repositories/       # Data access layer
│   ├── schemas/            # Pydantic request/response schemas
│   ├── services/           # Business service layer
│   └── main.py             # FastAPI application entrypoint
├── .env.example            # Example environment variables
├── Dockerfile              # Container image definition
├── docker-compose.yml      # Local app + PostgreSQL stack
├── requirements.txt        # Python dependencies
└── README.md
```

## Local run instructions

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create your local environment file:

```bash
cp .env.example .env
```

4. Start PostgreSQL.

You can use a local PostgreSQL instance or Docker Compose for the database service.

5. Run migrations:

```bash
alembic upgrade head
```

6. Start the API:

```bash
uvicorn app.main:app --reload
```

7. Verify endpoints:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/system/ping
curl http://127.0.0.1:8000/api/v1/market-data/status
curl http://127.0.0.1:8000/api/v1/market-data/latest
curl http://127.0.0.1:8000/api/v1/portfolio/summary
```

## Dashboard MVP

The current local dashboard is served by FastAPI at:

```text
http://127.0.0.1:8000/dashboard
```

It is a small static frontend for local simulator/demo usage. Current supported views and actions:

- bots list with local search/filter and stable frontend sorting
- selected bot summary with status, strategy, cooldown, last price, and last run time
- recent activity for the selected bot
- pause/resume for one bot
- manual `Run now` for one bot
- latest market price update form
- manual refresh
- optional auto-refresh every 10 seconds

Run it locally:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/dashboard`.

Important local note: app startup depends on the configured database being available. With the default settings this means PostgreSQL must be running; if PostgreSQL is unavailable, `uvicorn app.main:app --reload` will fail during startup.

## Manual demo guide

For a concise portfolio/demo walkthrough covering local startup, tests, `/health`, `/dashboard`, Binance price and candle smoke tests, and a sample backtest, see [docs/manual-demo-guide.md](docs/manual-demo-guide.md).

## Draft Balance checkpoint

Draft Balance is a bot-scoped test balance used by paper execution. The public API currently exposes only:

- `GET /api/v1/bots/{bot_id}/draft-balance`
- `POST /api/v1/bots/{bot_id}/draft-balance/reset`

The dashboard shows a selected-bot Draft Balance card under Paper Portfolio. Reset reinitializes only the selected bot's draft balance to the configured defaults and removes assets outside that reset/default set.

For paper execution with a real bot, BUY reserves the quote asset before paper portfolio mutation and applies the buy fill after the paper fill succeeds. SELL reserves the base asset before paper portfolio mutation and applies the sell fill after the paper fill succeeds. Missing or insufficient Draft Balance safely rejects paper execution before paper orders or fills are created; a manual bot run can return the existing safe skipped style: HTTP `200`, `action: skipped`, `message: order_rejected`.

Binance/testnet/live execution, broker submission, bot runner implementation, reconciliation jobs, and workers are not wired to Draft Balance.

## Paper Position / PnL checkpoint

Migration `20260618_0030` adds bot-scoped paper positions keyed by bot and symbol. Each position tracks `symbol`, `base_asset`, `quote_asset`, `quantity`, `average_entry_price`, and `realized_pnl`. When a cached local market price is available, the read view also includes optional `market_price`, `unrealized_pnl`, and `position_value`.

Paper BUY fills increase quantity and recalculate the weighted average entry price without changing realized PnL. Paper SELL fills reject overselling without mutation, decrease quantity, and realize PnL from the average cost basis. When quantity reaches zero, average entry resets safely to zero. Position updates are committed atomically with the paper order/fill, portfolio accounting, and Draft Balance mutation.

The public read-only endpoint is:

- `GET /api/v1/bots/{bot_id}/paper-position`

The selected-bot dashboard shows the Paper Position / PnL card between Paper Portfolio and Draft Balance. Missing local prices do not fail the request; market-derived fields remain unavailable until a cached local price exists.

Safety boundaries: this is paper-mode accounting only, uses cached local market data only, does not contact Binance, does not change live/testnet behavior or runner/scheduler behavior, and does not expose secrets or internal execution metadata.

### Paper Position / PnL runtime smoke closeout

The controlled runtime smoke passed with paused paper bot `6`, `Draft Balance BTC BUY Smoke Bot 20260617-1422`, after upgrading the local database from migration `20260616_0029` to `20260618_0030`.

- BUY at local price `50` created paper order `8` and fill `7`. Draft Balance moved from BTC `0` / USDT `10001.995501` to BTC `0.01` / USDT `10001.49475075`. Paper Position quantity moved from `0` to `0.01` with average entry `50.075025`.
- At local price `150`, position value was `1.5` and unrealized PnL was `0.99924975`.
- SELL at local price `250` created paper order `9` and fill `8`. Draft Balance returned to BTC `0` and USDT `10003.991002`. Paper Position closed with quantity `0`, average entry `0`, and realized PnL preserved at `1.995501`.

Final safety state: bot `6` remained paper mode and was paused. A pre-existing Binance WebSocket-enabled API was stopped before trade actions; the smoke API ran with market data, bot runner, testnet, and reconciliation workers disabled and was stopped afterward. No Binance endpoints, live/testnet commands, or runner/scheduler loops were used. Only PostgreSQL remained running, and the repository remained clean.

### Paper Trading Observability checkpoint

The Paper Trading Observability phase is complete. The selected-bot dashboard now includes Paper Equity visibility alongside paper orders, execution attempts, Draft Balance, and Paper Position / PnL. The Paper Equity card reads `GET /api/v1/bots/{bot_id}/paper-equity?limit=50`, shows the latest snapshot summary, and lists recent snapshots without polling or mutation controls.

Safe paused behavior was verified first with bot `6`, `Draft Balance BTC BUY Smoke Bot 20260617-1422`. A manual run while paused returned `action: skipped` with `message: bot_skipped_paused`; paper orders, execution attempts, Draft Balance, Paper Position, and Paper Equity snapshots did not change.

A controlled manual paper run was then completed for bot `6` using the Local Simulator and a local-only `BTCUSDT` price of `50`. The bot was resumed only for the single manual run, returned `action: bought` and `message: buy_filled`, then was stopped back to paused. The read-only API/dashboard data refreshed as expected:

- paper order and execution attempt advanced to new filled paper records
- Draft Balance moved BTC from `0` to `0.01` and USDT from `10003.991002` to `10003.49025175`
- Paper Position moved quantity from `0` to `0.01` with average entry `50.075025`
- Paper Equity snapshot count moved from `0` to `1`; latest snapshot `event_type` was `buy_fill` and `total_equity` was `10003.99025175`

Safety closeout: live trading was not enabled, Binance live/testnet behavior was not changed, periodic workers were not started, reconciliation worker status remained disabled/uninitialized with no jobs, and bot `6` was stopped back to paused. Repo hygiene note from the smoke: if present, pre-existing untracked `.hist.swp` and `hist` should be removed or ignored before claiming a final clean tree.

### Manual runtime smoke closeout

Draft Balance manual runtime smoke has been completed and closed out on the local Docker/API runtime. The controlled paper bot used for the final smoke was bot `6`, `BTCUSDT`, paper mode. It was paused after the smoke so it cannot accidentally continue running.

The BUY smoke used a local-only `BTCUSDT` market price of `50`. The paper BUY filled, Draft Balance BTC increased to `0.01`, and USDT decreased according to the paper fill, fee, and slippage rules. The SELL smoke used a local-only `BTCUSDT` market price of `250`. The paper SELL filled, Draft Balance BTC returned to `0`, and USDT increased to `10001.995501`.

The audit trail remained readable after cleanup: paper orders `6` and `7`, and paper execution attempts `6` and `7`, were preserved. Reconciliation stayed untouched: reconciliation jobs remained empty and the reconciliation worker stayed disabled/uninitialized.

Dashboard safety was also verified. The dashboard no longer auto-fetches Binance prices on startup, paper dashboard smoke no longer makes an automatic `/api/v1/market/binance/price` request, and explicit Binance price controls remain available for operator-triggered market-data fetches.

Safety closeout: no Binance/testnet/live order path was touched, no secrets or internal tokens were exposed in public API/dashboard output, the smoke bot was paused, and the repository was clean after verification.

### Bot-scoped paper execution safety checkpoint

Bot-scoped paper execution now settles BUY and SELL through the bot's own accounting surfaces. BUY mutates the selected bot's Draft Balance and Paper Position after the paper fill succeeds. SELL settles the bot-scoped Paper Position and Draft Balance first; any legacy/global paper portfolio SELL update is mirror-only and must not reject a valid bot-scoped SELL.

Settlement is treated as one logical unit across Order, Fill, ExecutionAttempt, DraftBalance, PaperPosition, and PaperEquitySnapshot. If settlement raises an `AppError`, provisional filled artifacts are rolled back and the run records a clean rejection instead of leaving partial filled state behind.

Duplicate execution protection is layered: the runner keeps the existing single-process lock, manual/API evaluations use DB-backed per-bot `SELECT ... FOR UPDATE` serialization, and the bot row lock is held through the full paper settlement critical section.

Runtime concurrency proof has passed in Local Simulator / paper mode only:

- two API processes issuing concurrent BUY produced one `buy_filled` and one `evaluation_no_signal`
- two API processes issuing concurrent SELL produced one `sell_filled` and one `evaluation_no_signal`
- duplicate orders, fills, execution attempts, and paper equity snapshots were not created
- Draft Balance and Paper Position mutated once per accepted fill

Safety boundaries: Binance/testnet/live behavior is unchanged and was not enabled or exercised. The reconciliation worker was not involved.

Current verification: full pytest `637 passed`; `py_compile` passed; `git diff --check` passed; Alembic head is `20260619_0031 (head)`.

## One-shot paper runner CLI

Use this operator CLI for controlled one-shot paper runner checks:

```bash
.venv/bin/python -m app.cli.run_bot_runner_once --bot-id <id>
```

In this project setup, the host `.env` may resolve the database host as `postgres`, which can fail from a host shell. Runtime/operator verification should usually run inside the API container:

```bash
docker-compose exec -T api python -m app.cli.run_bot_runner_once --bot-id <id>
```

Safety behavior:

- runs exactly one selected bot evaluation and exits
- paper mode only by default
- refuses testnet, live, and other non-paper bots
- respects the paused bot guard
- for paused bots, returns safe skipped JSON and creates no orders, fills, or execution attempts
- does not start the long-running runner loop
- does not start the reconciliation worker
- does not contact Binance by itself
- does not print credentials, raw payloads, headers, signed query data, broker internals, or tokens

Example paused output:

```json
{
  "action": "bot_paused",
  "bot_id": 6,
  "executed": false,
  "execution_attempts_created": 0,
  "execution_mode": "paper",
  "paper_fills_created": 0,
  "paper_orders_created": 0,
  "record_noop_events": false,
  "result": "skipped",
  "skipped": true,
  "status": "paused"
}
```

Use this CLI for controlled one-shot runner checks. Do not use the long-running runner for manual smoke verification unless explicitly testing runner lifecycle. For paper runtime smoke, set local market price through the existing local price API first if a strategy trigger is needed.

## Local paper demo smoke CLI

Use this operator CLI for a one-command local paper/demo BUY and SELL smoke:

```bash
.venv/bin/python -m app.cli.run_local_paper_demo_smoke
```

In the Docker Compose runtime, run it inside the API container so it uses the same database/network context as the app:

```bash
docker-compose exec -T api python -m app.cli.run_local_paper_demo_smoke
```

Safety behavior:

- local paper/demo mode only
- creates a fresh paper strategy, paper bot, and execution profile by default
- resets the selected bot's Draft Balance to USDT `10000` and BTC `0`
- uses local in-memory prices only: BUY at `95`, SELL at `115`
- forces live execution, Binance testnet broker, and Binance testnet order submission off inside the smoke runner
- does not start the long-running bot runner loop
- does not start the reconciliation worker
- pauses the smoke bot at the end, including failure cleanup

Example output:

```json
{
  "bot_id": 1,
  "buy_execution_attempt_id": 1,
  "buy_fill_id": 1,
  "buy_order_id": 1,
  "equity_snapshots_count": 2,
  "final_balance": "10001.968501",
  "final_bot_status": "paused",
  "final_position_quantity": "0",
  "initial_balance": "10000",
  "initial_position_quantity": "0",
  "mode": "local_paper_demo_only",
  "realized_pnl": "1.968501",
  "reconciliation_jobs_count": 0,
  "result": "PASS",
  "sell_execution_attempt_id": 2,
  "sell_fill_id": 2,
  "sell_order_id": 2
}
```

To use an existing paper bot instead of creating a fresh one:

```bash
.venv/bin/python -m app.cli.run_local_paper_demo_smoke --bot-id <paper_bot_id>
```

The selected bot must be paper mode and must not have an open paper position at the start of the smoke.

## CSV backtest CLI

Use this local CLI to backtest a `price_threshold` strategy against historical candles from a CSV file without fetching market data or creating runtime paper/live execution artifacts:

```bash
.venv/bin/python -m app.cli.run_backtest \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/BTCUSDT_1h_sample.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 95000 \
  --exit-above 105000 \
  --order-quantity 0.01
```

CSV format:

```csv
timestamp,open,high,low,close,volume
2025-01-01T00:00:00Z,95000,96000,94000,95500,123.45
```

The loader validates required columns, parseable timestamps, positive OHLC prices, non-negative volume, and duplicate timestamps. Candles are sorted by timestamp before simulation. At each candle, the strategy sees only the current and prior candles.

The CLI prints one JSON object containing summary metrics, trade details, and the equity curve. Use `--output-json <path>` to also write the same JSON payload to a file.

Print only compact summary JSON:

```bash
.venv/bin/python -m app.cli.run_backtest \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/BTCUSDT_1h_sample.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 95000 \
  --exit-above 105000 \
  --order-quantity 0.01 \
  --summary-only
```

Save comparable local results:

```bash
.venv/bin/python -m app.cli.run_backtest \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/BTCUSDT_1h_sample.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 95000 \
  --exit-above 105000 \
  --order-quantity 0.01 \
  --output-dir data/backtests/runs/demo_001
```

The output directory is created if needed. Existing `summary.json`, `trades.csv`, or `equity_curve.csv` files are not overwritten unless `--overwrite` is provided. Generated run directories under `data/backtests/runs/` are ignored by git.

Generated files:

- `summary.json`: compact metrics for comparing runs
- `trades.csv`: one row per simulated buy/sell
- `equity_curve.csv`: one row per candle with equity and drawdown

## Prepare CSV backtest datasets

Put downloaded or exported raw OHLCV CSV files under `data/backtests/raw/`. Generated prepared datasets belong under `data/backtests/datasets/`; both directories are ignored by git so large local history files do not get committed.

Prepare one canonical dataset from one or more raw files:

```bash
.venv/bin/python -m app.cli.prepare_backtest_dataset \
  --symbol BTCUSDT \
  --timeframe 1h \
  --input data/backtests/raw/BTCUSDT_1h_2025.csv \
  --input data/backtests/raw/BTCUSDT_1h_2026.csv \
  --output data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --summary-json data/backtests/datasets/BTCUSDT_1h_prepared.summary.json
```

Optional date filters use start-inclusive and end-exclusive UTC boundaries:

```bash
--start 2025-01-01 --end 2026-01-01
```

The prepared CSV uses the same format as the backtest CLI:

```csv
timestamp,open,high,low,close,volume
2025-01-01T00:00:00Z,95000,96000,94000,95500,123.45
```

The preparation tool accepts common timestamp column names such as `timestamp`, `open_time`, `time`, and `date`, validates OHLCV values, sorts candles chronologically, reports duplicate timestamps and missing intervals, and refuses to overwrite output unless `--overwrite` is passed. If duplicate timestamps are expected, use `--dedupe keep-first` or `--dedupe keep-last`.

Run a backtest on the prepared dataset:

```bash
.venv/bin/python -m app.cli.run_backtest \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 95000 \
  --exit-above 105000 \
  --order-quantity 0.01 \
  --summary-only
```

This is local historical simulation only. It does not fetch Binance data, place orders, or write runtime paper/live execution records.

## Prepared backtest smoke

Use this local smoke flow after preparing a canonical CSV dataset. It proves the path from prepared CSV to saved backtest output, and can optionally compare the new summary with a previous saved run.

Prepare a dataset:

```bash
.venv/bin/python -m app.cli.prepare_backtest_dataset \
  --symbol BTCUSDT \
  --timeframe 1h \
  --input data/backtests/raw/BTCUSDT_1h_2025.csv \
  --output data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --summary-json data/backtests/datasets/BTCUSDT_1h_prepared.summary.json
```

Run the prepared dataset smoke:

```bash
.venv/bin/python -m app.cli.run_prepared_backtest_smoke \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 95000 \
  --exit-above 105000 \
  --order-quantity 0.01 \
  --output-dir data/backtests/runs/BTCUSDT_1h_smoke_001
```

Compare with a previous run summary:

```bash
.venv/bin/python -m app.cli.run_prepared_backtest_smoke \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 95000 \
  --exit-above 105000 \
  --order-quantity 0.01 \
  --output-dir data/backtests/runs/BTCUSDT_1h_smoke_002 \
  --compare-summary data/backtests/runs/BTCUSDT_1h_smoke_001/summary.json
```

Outputs are saved under the chosen `data/backtests/runs/...` directory:

- `summary.json`: compact smoke summary and optional comparison deltas
- `trades.csv`: simulated trade rows
- `equity_curve.csv`: simulated equity and drawdown per candle

This smoke is local-only. It does not fetch Binance data, place live/testnet orders, invoke the bot runner, or create runtime paper/live audit records.

## Compare saved backtest runs

After saving two local smoke runs, compare their file artifacts without rerunning a strategy:

```bash
.venv/bin/python -m app.cli.run_prepared_backtest_smoke \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 95000 \
  --exit-above 105000 \
  --order-quantity 0.01 \
  --output-dir data/backtests/runs/BTCUSDT_1h_smoke_base

.venv/bin/python -m app.cli.run_prepared_backtest_smoke \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 96000 \
  --exit-above 104000 \
  --order-quantity 0.01 \
  --output-dir data/backtests/runs/BTCUSDT_1h_smoke_candidate
```

Compare the saved run directories:

```bash
.venv/bin/python -m app.cli.compare_backtest_runs \
  --base-run-dir data/backtests/runs/BTCUSDT_1h_smoke_base \
  --candidate-run-dir data/backtests/runs/BTCUSDT_1h_smoke_candidate \
  --compact
```

Write the same JSON report to a file:

```bash
.venv/bin/python -m app.cli.compare_backtest_runs \
  --base-run-dir data/backtests/runs/BTCUSDT_1h_smoke_base \
  --candidate-run-dir data/backtests/runs/BTCUSDT_1h_smoke_candidate \
  --output-json data/backtests/runs/BTCUSDT_1h_comparison.json
```

The comparison reads `summary.json`, `trades.csv`, and `equity_curve.csv` from each run directory. Missing optional metrics are reported as unavailable. This helper is local-only and file-based; it does not fetch market data, place orders, invoke the bot runner, write database rows, or create runtime paper/live audit records.

## Export a backtest Markdown report

After saving a prepared dataset smoke run, optionally compare it with another run, then export a human-readable Markdown report:

```bash
.venv/bin/python -m app.cli.run_prepared_backtest_smoke \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 95000 \
  --exit-above 105000 \
  --order-quantity 0.01 \
  --output-dir data/backtests/runs/BTCUSDT_1h_smoke_base

.venv/bin/python -m app.cli.run_prepared_backtest_smoke \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 96000 \
  --exit-above 104000 \
  --order-quantity 0.01 \
  --output-dir data/backtests/runs/BTCUSDT_1h_smoke_candidate

.venv/bin/python -m app.cli.compare_backtest_runs \
  --base-run-dir data/backtests/runs/BTCUSDT_1h_smoke_base \
  --candidate-run-dir data/backtests/runs/BTCUSDT_1h_smoke_candidate \
  --output-json data/backtests/runs/BTCUSDT_1h_comparison.json
```

Export Markdown:

```bash
.venv/bin/python -m app.cli.export_backtest_report \
  --run-dir data/backtests/runs/BTCUSDT_1h_smoke_candidate \
  --comparison-json data/backtests/runs/BTCUSDT_1h_comparison.json \
  --output-md data/backtests/runs/BTCUSDT_1h_report.md \
  --title "BTCUSDT 1h Backtest Report"
```

The report includes run metadata, strategy/config fields when available, key performance metrics, artifact row counts, optional comparison deltas, and a local-simulation safety note. This exporter is local-only and file-based; it does not fetch market data, place orders, invoke the bot runner, write database rows, or create runtime paper/live audit records.

## Export a backtest demo bundle

Package a saved run, optional comparison, and optional Markdown report into a clean review folder:

```bash
.venv/bin/python -m app.cli.run_prepared_backtest_smoke \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 95000 \
  --exit-above 105000 \
  --order-quantity 0.01 \
  --output-dir data/backtests/runs/BTCUSDT_1h_smoke_base

.venv/bin/python -m app.cli.run_prepared_backtest_smoke \
  --symbol BTCUSDT \
  --timeframe 1h \
  --csv data/backtests/datasets/BTCUSDT_1h_prepared.csv \
  --initial-balance 10000 \
  --fee-rate 0.001 \
  --strategy-type price_threshold \
  --entry-below 96000 \
  --exit-above 104000 \
  --order-quantity 0.01 \
  --output-dir data/backtests/runs/BTCUSDT_1h_smoke_candidate

.venv/bin/python -m app.cli.compare_backtest_runs \
  --base-run-dir data/backtests/runs/BTCUSDT_1h_smoke_base \
  --candidate-run-dir data/backtests/runs/BTCUSDT_1h_smoke_candidate \
  --output-json data/backtests/runs/BTCUSDT_1h_comparison.json

.venv/bin/python -m app.cli.export_backtest_report \
  --run-dir data/backtests/runs/BTCUSDT_1h_smoke_candidate \
  --comparison-json data/backtests/runs/BTCUSDT_1h_comparison.json \
  --output-md data/backtests/runs/BTCUSDT_1h_report.md \
  --title "BTCUSDT 1h Backtest Report"
```

Export the demo bundle:

```bash
.venv/bin/python -m app.cli.export_backtest_demo_bundle \
  --run-dir data/backtests/runs/BTCUSDT_1h_smoke_candidate \
  --comparison-json data/backtests/runs/BTCUSDT_1h_comparison.json \
  --report-md data/backtests/runs/BTCUSDT_1h_report.md \
  --output-dir data/backtests/runs/BTCUSDT_1h_demo_bundle \
  --title "BTCUSDT 1h Demo Bundle"
```

The bundle contains `summary.json`, optional `trades.csv`, optional `equity_curve.csv`, optional `comparison.json`, optional `report.md`, `manifest.json`, and `README.md`. The manifest records the source run directory, included files, optional unavailable files, CSV row counts, and SHA256 checksums for included deliverable files. Existing non-empty bundle directories are refused unless `--overwrite` is passed.

This exporter is local-only and file-based. It does not include raw datasets by default, fetch market data, place orders, invoke the bot runner, write database rows, or create runtime paper/live audit records.

## Backtest demo pipeline reference

For the concise one-command workflow, prepared CSV shortcut, and generated folder structure, see [Local Backtest Demo Pipeline](#local-backtest-demo-pipeline). The component CLIs above are useful when presenting each stage separately: dataset preparation, saved smoke run, comparison JSON, Markdown report, and demo bundle export.

Backtest safety behavior:

- pure local simulation over CSV data
- no Binance, testnet, live, or network calls
- no paper/live `Order`, `Fill`, `ExecutionAttempt`, or reconciliation records
- no database migrations or persisted backtest rows

## Safe paper demo checklist

Use this checklist before presenting the dashboard or paper runtime flow:

- confirm the repository is clean with `git status --short`
- start the local Docker Compose stack
- verify `http://127.0.0.1:8000/health` returns OK
- verify the API container database is at the current Alembic head
- confirm the bot runner and reconciliation worker are disabled unless that lifecycle is the explicit demo subject

Paper dashboard demo:

- use paper bots only
- keep testnet and live bots paused
- confirm the dashboard does not auto-fetch Binance prices on startup
- use the Draft Balance and Recent Paper Orders cards as safe paper-mode views
- use explicit Binance price buttons only when intentionally demonstrating market-data fetches

One-shot runner demo:

```bash
docker-compose exec -T api python -m app.cli.run_bot_runner_once --bot-id <paper_bot_id>
```

For paused bots, the expected result is safe skipped JSON with no orders, fills, or execution attempts created. Do not use the long-running runner for simple demo checks.

Draft Balance reset guidance:

- reset affects only the selected bot's Draft Balance
- reset does not delete paper orders or execution attempts
- reset does not touch Binance, testnet, live, reconciliation, or worker paths

Safety checklist before any demo:

- no Binance, testnet, or live order submission
- no reconciliation worker started
- no unexpected `/api/v1/market/binance/price` calls
- no credentials, secrets, tokens, headers, signed query data, raw payloads, or raw responses in public dashboard/API output

Current known smoke bot: bot `6` is a paused paper smoke bot from the controlled BUY/SELL verification. Keep it paused unless intentionally using it for paper-only smoke.

## Binance testnet reconciliation command

This internal command processes one bounded batch of delayed Binance Spot testnet reconciliation jobs and exits:

```bash
.venv/bin/python -m app.cli.process_binance_testnet_reconciliation
```

To override the configured batch size for that one run:

```bash
.venv/bin/python -m app.cli.process_binance_testnet_reconciliation --batch-size 10
```

This pass does not install a scheduler, cron job, background loop, or daemon.

## Binance Spot Testnet Smoke Workflow

Use this only with Binance Spot testnet credentials. Do not put live Binance credentials in `.env`.

Execution modes are intentionally separate:

- paper mode mutates only the local simulated portfolio
- testnet mode uses Binance Spot testnet HTTP requests and does not mutate the paper portfolio
- live mode is blocked and records `live_mode_not_implemented`
- the reconciliation CLI is an internal one-shot command that processes one batch and exits
- no scheduler is installed yet

Current checkpoint:

- The Binance Spot testnet path has been historically proven by execution attempt `5`, created at `2026-06-09T20:33:52Z`: `bot_id=4`, `mode=testnet`, `broker=binance_testnet`, `side=buy`, `quantity=0.001`, `dry_run=false`, `final_status=order_created`, `status_code=200`, and `exchange_status=FILLED`.
- Use the manual one-shot API path, `POST /api/v1/bots/{bot_id}/run`, for any future controlled smoke. It runs one synchronous evaluation for the chosen bot and does not start the periodic runner loop.
- Runner-based testnet smoke is not recommended unless a periodic-loop scenario is specifically being tested.
- Keep live execution disabled, keep `BINANCE_TESTNET_DRY_RUN_ENABLED=true` by default, keep the testnet bot paused by default, and keep `BOT_RUNNER_ENABLED=false` unless intentionally testing the runner.
- Known successful testnet execution does not mutate the paper portfolio and should leave no unresolved delayed-reconciliation work.
- Public read APIs intentionally avoid exposing internal correlation fields such as `client_order_id` and exchange order id. Add an operator-only correlation surface later only if there is a concrete operational need.

1. Copy `.env.example` to `.env`, then configure testnet-only values:

```bash
BINANCE_TESTNET_BROKER_ENABLED=true
BINANCE_TESTNET_ORDER_SUBMISSION_ENABLED=true
BINANCE_TESTNET_API_KEY=<SPOT_TESTNET_API_KEY>
BINANCE_TESTNET_API_SECRET=<SPOT_TESTNET_API_SECRET>
BINANCE_TESTNET_BASE_URL=https://testnet.binance.vision
BINANCE_TESTNET_TIMEOUT_SECONDS=5
BINANCE_TESTNET_RECV_WINDOW=5000
BINANCE_TESTNET_DRY_RUN_ENABLED=true
EXECUTION_LIVE_ENABLED=false
```

2. Start the local app with the normal local workflow:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

3. Verify health:

```bash
curl http://127.0.0.1:8000/health
```

4. Inspect execution safety before enabling a test bot:

```bash
curl "http://127.0.0.1:8000/api/v1/execution-safety/status?mode=testnet&broker=binance_testnet&side=buy&quantity=<TINY_QUANTITY>&market_price=<LATEST_PRICE>"
```

Confirm the response shows testnet submission enabled, credentials configured, dry-run enabled, live execution disabled, and no blocking reason for the tiny testnet order.

5. Create or use a dedicated test strategy and bot. The bot must use `execution_mode=testnet`:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BTC Testnet Smoke",
    "symbol": "BTCUSDT",
    "timeframe": "1m",
    "strategy_type": "price_threshold",
    "parameters": {},
    "is_active": true,
  }'

curl -X POST http://127.0.0.1:8000/api/v1/bots \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BTC Testnet Smoke Bot",
    "strategy_id": <STRATEGY_ID>,
    "exchange_name": "binance_testnet",
    "status": "active",
    "is_paper": false,
    "execution_mode": "testnet",
    "notes": "Manual Spot testnet smoke only"
  }'
```

6. Configure the bot execution profile and local price so the existing manual run path can produce a tiny signal:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bots/<BOT_ID>/execution-profile \
  -H "Content-Type: application/json" \
  -d '{
    "max_position_size_usd": 25,
    "max_daily_loss_usd": 25,
    "max_open_positions": 1,
    "strategy_type": "price_threshold",
    "entry_below": "<BUY_AT_OR_ABOVE_LATEST_PRICE>",
    "exit_above": "<SELL_THRESHOLD>",
    "order_quantity": "<TINY_QUANTITY>",
    "default_order_type": "market",
    "is_enabled": true
  }'

curl -X POST http://127.0.0.1:8000/api/v1/market/price \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "price": "<LATEST_PRICE>"
  }'
```

7. Run the bot once while dry-run is still enabled:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bots/<BOT_ID>/run
curl "http://127.0.0.1:8000/api/v1/bots/<BOT_ID>/execution-attempts?mode=testnet&limit=5"
```

Confirm the attempt is safe metadata only and reports `testnet_order_submission_dry_run`.

8. Only after the dry-run attempt is correct, set `BINANCE_TESTNET_DRY_RUN_ENABLED=false`, restart the app, and run one tiny testnet-only order:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bots/<BOT_ID>/run
curl "http://127.0.0.1:8000/api/v1/bots/<BOT_ID>/execution-attempts?mode=testnet&limit=5"
```

9. If the attempt is status-unknown or unresolved, inspect reconciliation status:

```bash
curl "http://127.0.0.1:8000/api/v1/bots/<BOT_ID>/execution-reconciliation/status?limit=20"
```

Manual reconciliation for one unresolved attempt uses the persisted identifiers:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bots/<BOT_ID>/execution-attempts/<ATTEMPT_ID>/reconcile
```

Run the internal one-shot CLI only when a delayed reconciliation job is due and you intentionally want one bounded batch:

```bash
.venv/bin/python -m app.cli.process_binance_testnet_reconciliation --batch-size 1
```

10. Restore `BINANCE_TESTNET_DRY_RUN_ENABLED=true` after the smoke test and restart the app.

Recommended next development options:

- Improve operator-facing visibility for execution attempts in the frontend while preserving the existing safe metadata allowlist.
- Add an optional internal/operator-only correlation field later if Binance UI correlation becomes necessary.
- Harden production-readiness around configuration checks, runbooks, and startup/preflight clarity before expanding broker scope.
- Continue paper/draft balance and operator workflow improvements before any live-mode work.

## Docker run instructions

```bash
cp .env.example .env
docker compose up --build
```

The API will be available at `http://127.0.0.1:8000`.

## Market data slice

This step adds the first real market-data vertical slice:

- `app/data/schemas.py` defines the normalized internal market event model
- `app/data/providers/base.py` defines the provider abstraction
- `app/data/providers/binance.py` implements a minimal Binance public WebSocket ticker provider
- `app/services/market_data_service.py` runs the provider, tracks the latest in-memory state, and exposes service health
- `GET /api/v1/market-data/status` returns runtime status
- `GET /api/v1/market-data/latest` returns the latest normalized event snapshot

Current limitations:

- only one provider is implemented: `binance`
- only one symbol is streamed at a time
- only one event type is normalized: ticker-style updates
- market data is held only in memory and is lost on restart
- there is no strategy execution, risk engine, real broker execution, or notifications yet

## Market data configuration

Add these variables to `.env` if you want to change the default feed:

```bash
MARKET_DATA_ENABLED=true
MARKET_DATA_PROVIDER=binance
MARKET_DATA_SYMBOL=BTCUSDT
MARKET_DATA_WEBSOCKET_URL=wss://stream.binance.com:9443/ws
MARKET_DATA_RECONNECT_DELAY_SECONDS=2
MARKET_DATA_INCLUDE_RAW_PAYLOAD=false
```

Defaults:

- provider: `binance`
- symbol: `BTCUSDT`
- stream: `<symbol>@ticker`

## Market data endpoints

Check service status:

```bash
curl http://127.0.0.1:8000/api/v1/market-data/status
```

Fetch all latest normalized events currently held in memory:

```bash
curl http://127.0.0.1:8000/api/v1/market-data/latest
```

Fetch the latest event for one symbol:

```bash
curl "http://127.0.0.1:8000/api/v1/market-data/latest?symbol=BTCUSDT"
```

Example status response before the first event arrives:

```json
{
  "running": true,
  "enabled": true,
  "provider": "binance",
  "symbol": "BTCUSDT",
  "last_received_event_ts": null,
  "last_received_at": null,
  "received_event_count": 0
}
```

## Portfolio and simulated execution slice

This step adds the first persisted paper-trading foundation:

- `portfolio_accounts` stores one virtual cash account
- `positions` stores current long-only symbol state and realized PnL by symbol
- `simulated_orders` stores accepted and rejected market order requests
- `simulated_fills` stores one fill per accepted order
- portfolio summary and positions endpoints expose current paper account state
- simulated market orders use the latest price already held by the in-memory market data service

How simulated execution works:

- the app ensures one portfolio account row exists on startup
- the default account starts with `1000.00 USD` and is not reset on restart
- market buy and sell requests look up the latest in-memory price for the requested symbol
- buy orders apply positive slippage and a fee, then reduce cash and increase the position
- sell orders apply negative slippage and a fee, then increase cash and reduce the position
- only long positions are supported, and sells larger than the current position are rejected
- if no latest price is available, the order is rejected and stored as a rejected simulated order

Simulation configuration:

```bash
SIMULATION_ENABLED=true
SIMULATION_BASE_CURRENCY=USD
SIMULATION_STARTING_CASH=1000.00
SIMULATION_FEE_BPS=10
SIMULATION_SLIPPAGE_BPS=5
```

Current limitations:

- one account only
- long-only positions only
- market orders only
- latest known price only
- one fill per order
- no strategy engine
- no background trading loop
- no stop-loss, take-profit, or risk controls yet
- no advanced portfolio analytics or tax/accounting logic yet

## Automated bot runner slice

This step makes the existing `Strategy`, `Bot`, `ExecutionProfile`, `BotRun`, and `RunEvent` domain actually functional for one simple automated rule.

Supported strategy type:

- `price_threshold`

Rule behavior:

- if there is no open long position for the bot symbol and `latest_price <= entry_below`, the runner submits a simulated market buy
- if there is an open long position for the bot symbol and `latest_price >= exit_above`, the runner submits a simulated market sell for the full open quantity

Where configuration lives:

- `Strategy.symbol` defines the trading symbol
- `Bot.status` controls whether the bot is active or paused
- `ExecutionProfile.is_enabled` acts as the execution enable flag
- `ExecutionProfile.strategy_type`, `entry_below`, `exit_above`, and `order_quantity` hold the rule configuration

How the bot runner works:

- a background task scans active bots on a fixed polling interval
- it reads the latest price from the existing in-memory market data service
- it evaluates the `price_threshold` rule
- it sends simulated buy/sell orders through the existing simulated execution service
- it persists `BotRun` sessions and `RunEvent` timeline entries for start, stop, skipped evaluations, signals, fills, rejections, and errors

Runner configuration:

```bash
BOT_RUNNER_ENABLED=true
BOT_RUNNER_POLL_INTERVAL_SECONDS=2
```

Current limitations:

- only one supported rule type: `price_threshold`
- long-only
- market orders only
- no indicators
- no scale-in or scale-out
- no advanced risk engine
- no stop-loss / take-profit framework
- no multi-exchange logic
- no real-money execution

Start a bot:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bots/1/start
```

Stop a bot:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bots/1/stop
```

Check bot status:

```bash
curl http://127.0.0.1:8000/api/v1/bots/1/status
```

List bot runs:

```bash
curl "http://127.0.0.1:8000/api/v1/bot-runs?bot_id=1"
```

List bot run events:

```bash
curl "http://127.0.0.1:8000/api/v1/run-events?bot_id=1"
```

Portfolio summary:

```bash
curl http://127.0.0.1:8000/api/v1/portfolio/summary
```

Open positions:

```bash
curl http://127.0.0.1:8000/api/v1/portfolio/positions
```

Simulated market buy:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/execution/market-order \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "side": "buy",
    "quantity": "0.001"
  }'
```

Simulated market sell:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/execution/market-order \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "side": "sell",
    "quantity": "0.001"
  }'
```

Order and fill history:

```bash
curl http://127.0.0.1:8000/api/v1/execution/orders
curl http://127.0.0.1:8000/api/v1/execution/fills
```

## Strategy entity

`Strategy` is the first persisted business entity in the platform. It is a simple configuration placeholder for a future trading strategy and currently stores:

- `name`
- `description`
- `symbol`
- `timeframe`
- `is_active`
- `created_at`
- `updated_at`

It is intentionally limited to metadata and configuration only.

## Bot entity

`Bot` represents a future automation instance attached to a strategy. For now it is also metadata only and stores:

- `name`
- `strategy_id`
- `exchange_name`
- `status`
- `is_paper`
- `notes`
- `created_at`
- `updated_at`

Each bot belongs to a strategy and is intended to become the future operational wrapper around a strategy configuration.

## ExecutionProfile entity

`ExecutionProfile` represents runtime and risk configuration attached to a bot. For now it is configuration only and stores:

- `bot_id`
- `max_position_size_usd`
- `max_daily_loss_usd`
- `max_open_positions`
- `default_order_type`
- `is_enabled`
- `created_at`
- `updated_at`

Each bot can have at most one execution profile. This keeps the relationship simple while giving the platform a clear place to store future operational and risk settings.

## BotRun entity

`BotRun` represents a historical record of a bot run request or lifecycle attempt. It stores:

- `bot_id`
- `trigger_type`
- `status`
- `summary`
- `error_message`
- `started_at`
- `finished_at`
- `created_at`
- `updated_at`

Each bot can accumulate many bot runs over time. BotRun is treated as audit/history data rather than normal editable configuration, which is why there is no delete endpoint for runs at this stage.

## RunEvent entity

`RunEvent` represents the append-only event timeline for a bot run. It stores:

- `bot_run_id`
- `event_type`
- `level`
- `message`
- `payload`
- `created_at`

RunEvents are intended for operational notes, lifecycle transitions, warnings, and errors. They are not editable configuration, which is why there are no update or delete endpoints for events at this stage.

Lifecycle events are created automatically when a bot run is requested and when its status changes, giving each run a useful built-in timeline from the start.

## Database and migrations

Alembic is wired to the application's SQLAlchemy metadata and includes migrations for the `strategies`, `bots`, `execution_profiles`, `bot_runs`, and `run_events` tables.

Run the current migrations:

```bash
alembic upgrade head
```

Create future autogenerated migrations after model changes:

```bash
alembic revision --autogenerate -m "describe your change"
```

Rollback one migration if needed:

```bash
alembic downgrade -1
```

## API examples

Create a strategy:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mean Reversion Placeholder",
    "description": "Initial metadata-only strategy",
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "is_active": true
  }'
```

List strategies:

```bash
curl http://127.0.0.1:8000/api/v1/strategies
```

Get a strategy by id:

```bash
curl http://127.0.0.1:8000/api/v1/strategies/1
```

Partially update a strategy:

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/strategies/1 \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description",
    "is_active": false
  }'
```

Delete a strategy:

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/strategies/1
```

Create a bot:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bots \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BTC Paper Bot",
    "strategy_id": 1,
    "exchange_name": "Binance",
    "status": "draft",
    "is_paper": true,
    "notes": "First bot placeholder"
  }'
```

List bots:

```bash
curl http://127.0.0.1:8000/api/v1/bots
```

List bots filtered by strategy:

```bash
curl "http://127.0.0.1:8000/api/v1/bots?strategy_id=1"
```

Get a bot by id:

```bash
curl http://127.0.0.1:8000/api/v1/bots/1
```

Partially update a bot:

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/bots/1 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "active",
    "notes": "Ready for future activation"
  }'
```

Delete a bot:

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/bots/1
```

Create an execution profile for a bot:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bots/1/execution-profile \
  -H "Content-Type: application/json" \
  -d '{
    "max_position_size_usd": 500.0,
    "max_daily_loss_usd": 150.0,
    "max_open_positions": 2,
    "default_order_type": "limit",
    "is_enabled": true
  }'
```

Get a bot execution profile:

```bash
curl http://127.0.0.1:8000/api/v1/bots/1/execution-profile
```

Partially update a bot execution profile:

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/bots/1/execution-profile \
  -H "Content-Type: application/json" \
  -d '{
    "max_daily_loss_usd": 200.0,
    "default_order_type": "market"
  }'
```

Delete a bot execution profile:

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/bots/1/execution-profile
```

Create a bot run:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bots/1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "trigger_type": "manual"
  }'
```

List bot runs:

```bash
curl http://127.0.0.1:8000/api/v1/bots/1/runs
```

Get a bot run by id:

```bash
curl http://127.0.0.1:8000/api/v1/bots/1/runs/1
```

Move a bot run to running:

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/bots/1/runs/1 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "running",
    "summary": "Run started"
  }'
```

Move a bot run to succeeded:

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/bots/1/runs/1 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "succeeded",
    "summary": "Run completed without execution"
  }'
```

List run events:

```bash
curl http://127.0.0.1:8000/api/v1/bots/1/runs/1/events
```

Get a run event by id:

```bash
curl http://127.0.0.1:8000/api/v1/bots/1/runs/1/events/1
```

Create a manual run event:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bots/1/runs/1/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "log",
    "level": "info",
    "message": "Dry validation checks completed",
    "payload": {
      "checks_passed": true
    }
  }'
```

## Architectural choices

- Backend-first and modular: the codebase is split by responsibility so strategy execution, exchange integrations, notifications, jobs, and risk modules can be added without collapsing into a single large app module.
- Production-minded, minimal surface area: the current code includes only the primitives needed to run a service reliably and evolve it safely.
- PostgreSQL-ready from day one: SQLAlchemy and Alembic are configured around a PostgreSQL connection string, while remaining small enough for easy iteration.

## Intentionally left for future steps

- Strategy orchestration and execution logic
- Exchange and broker integrations
- Authentication and authorization
- Background workers and schedulers
- Telegram integration
- Risk management policies and limits
- Configuration UI and richer web dashboard
- Metrics, tracing, and richer operational tooling

## Exact local commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```
