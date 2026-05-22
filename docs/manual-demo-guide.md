# Manual Demo Guide

This guide is for a local portfolio demo of the trading automation platform. The current product is a paper/simulation-focused system: it can ingest public Binance market data, store candles, run strategy backtests, show a local dashboard, and execute simulated orders. It does not place real-money trades.

## Start Locally

From the repository root:

```bash
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload
```

The app expects the configured database to be available. With the default `.env.example` settings, that means PostgreSQL must be running locally or through Docker Compose.

If you are setting up from scratch:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Run Tests

Run the full backend test suite with the project virtualenv:

```bash
.venv/bin/python -m pytest tests
```

Check Alembic has a single migration head:

```bash
.venv/bin/alembic heads
```

## Check Health

```bash
curl -i http://127.0.0.1:8000/health
```

Expected result:

```json
{"status":"ok"}
```

## Open The Dashboard

Open this URL in a browser:

```text
http://127.0.0.1:8000/dashboard
```

The dashboard is a local simulator/demo UI for bots, strategy parameters, risk settings, recent activity, market price updates, Binance candle import, backtests, and optimization workflows.

## Smoke Test Binance Price

This checks the explicit Binance REST price fetch and stores the latest simulated market price in the in-memory market data service.

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/market/binance/price \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT"}'
```

Expected shape:

```json
{
  "symbol": "BTCUSDT",
  "price": "65000.12",
  "updated_at": "2026-05-22T20:01:05.000000Z",
  "source": "binance"
}
```

The exact price and timestamp will vary.

## Smoke Test Binance Candles

This imports recent Binance candles into the persisted candle table for later backtests.

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/market/binance/candles \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","timeframe":"1m","limit":10}'
```

Expected shape:

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "1m",
  "source": "binance",
  "requested_limit": 10,
  "stored_count": 10,
  "candles": []
}
```

The `candles` array contains the stored candle records. Supported Binance intervals include `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1w`, and `1M`; unsupported intervals such as `2m` should return validation errors instead of reaching Binance.

## Run A Backtest

Backtests run against persisted candles. For a simple demo, import Binance candles first, create a strategy, then run the backtest using `source: "binance"`.

Create a strategy:

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BTC Demo Threshold",
    "description": "Portfolio demo strategy for simulated backtesting",
    "symbol": "BTCUSDT",
    "timeframe": "1m",
    "strategy_type": "price_threshold",
    "parameters": {
      "buy_below": "65000",
      "sell_above": "70000",
      "quantity": "0.001"
    },
    "is_active": true
  }'
```

Use the returned `id` as `strategy_id`:

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/backtests \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": 1,
    "initial_balance": "10000",
    "source": "binance"
  }'
```

Expected response fields include `strategy_id`, `symbol`, `timeframe`, `strategy_type`, `source`, `initial_balance`, `final_balance`, `number_of_trades`, `closed_trades`, `candles_processed`, return metrics, and a `trades` list. A no-trade result is still a valid result when the saved thresholds do not trigger on the imported candle data.

## What The Demo Proves

- FastAPI backend with versioned REST endpoints and centralized validation/error handling.
- PostgreSQL-ready persistence with SQLAlchemy and Alembic migrations.
- Public Binance market data integration for latest price and historical candles.
- Paper/simulated portfolio and market-order execution flows, not live broker execution.
- Strategy configuration, bot metadata, execution profiles, run history, and append-only activity events.
- Backtesting and optimization workflows over persisted candle data.
- Local dashboard for operating the simulation-oriented workflows.
- Release-readiness basics: full backend tests, migration-head check, and health endpoint verification.

## Honest Limitations

- This is not a live trading system and does not execute real broker orders.
- The Binance integration uses public market data endpoints only.
- Authentication, authorization, production observability, and real-money risk controls are outside the current scope.
- Demo results depend on the local database state and the market candles imported before running a backtest.
