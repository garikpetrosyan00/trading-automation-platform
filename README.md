# Trading Automation Platform

This repository provides the initial backend foundation for a production-style trading automation platform. The current scope is intentionally narrow: it sets up a clean FastAPI application skeleton, environment-based configuration, database and migration scaffolding, logging, basic exception handling, starter Docker files, the first real market-data ingestion slice, and the first persisted virtual portfolio and simulated execution slice.

The first business entities, `Strategy`, `Bot`, `ExecutionProfile`, `BotRun`, and `RunEvent`, are now included as stored metadata/configuration records. At this stage none of them executes trades. They are only persisted and managed through the REST API.

Production broker integrations, Telegram notifications, production dashboards, scheduler deployment, authentication, and advanced risk workflows are intentionally left for later steps.

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

### Manual runtime smoke closeout

Draft Balance manual runtime smoke has been completed and closed out on the local Docker/API runtime. The controlled paper bot used for the final smoke was bot `6`, `BTCUSDT`, paper mode. It was paused after the smoke so it cannot accidentally continue running.

The BUY smoke used a local-only `BTCUSDT` market price of `50`. The paper BUY filled, Draft Balance BTC increased to `0.01`, and USDT decreased according to the paper fill, fee, and slippage rules. The SELL smoke used a local-only `BTCUSDT` market price of `250`. The paper SELL filled, Draft Balance BTC returned to `0`, and USDT increased to `10001.995501`.

The audit trail remained readable after cleanup: paper orders `6` and `7`, and paper execution attempts `6` and `7`, were preserved. Reconciliation stayed untouched: reconciliation jobs remained empty and the reconciliation worker stayed disabled/uninitialized.

Dashboard safety was also verified. The dashboard no longer auto-fetches Binance prices on startup, paper dashboard smoke no longer makes an automatic `/api/v1/market/binance/price` request, and explicit Binance price controls remain available for operator-triggered market-data fetches.

Safety closeout: no Binance/testnet/live order path was touched, no secrets or internal tokens were exposed in public API/dashboard output, the smoke bot was paused, and the repository was clean after verification.

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
