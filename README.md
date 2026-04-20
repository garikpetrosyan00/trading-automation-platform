# Trading Automation Platform

This repository provides the initial backend foundation for a production-style trading automation platform. The current scope is intentionally narrow: it sets up a clean FastAPI application skeleton, environment-based configuration, database and migration scaffolding, logging, basic exception handling, starter Docker files, the first real market-data ingestion slice, and the first persisted virtual portfolio and simulated execution slice.

The first business entities, `Strategy`, `Bot`, `ExecutionProfile`, `BotRun`, and `RunEvent`, are now included as stored metadata/configuration records. At this stage none of them executes trades. They are only persisted and managed through the REST API.

Trading logic, broker integrations, Telegram notifications, dashboards, background jobs, authentication, and risk workflows are intentionally left for later steps.

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
- Configuration UI and web dashboard
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
