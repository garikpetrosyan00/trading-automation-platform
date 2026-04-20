from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.engine.bot_runner import BotRunner
from app.services.market_data_service import MarketDataService


def get_db_session(request: Request):
    session_factory = getattr(request.app.state, "db_session_factory", SessionLocal)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db_session)]


def get_market_data_service(request: Request) -> MarketDataService:
    return request.app.state.market_data_service


MarketDataServiceDep = Annotated[MarketDataService, Depends(get_market_data_service)]


def get_bot_runner(request: Request) -> BotRunner:
    return request.app.state.bot_runner


BotRunnerDep = Annotated[BotRunner, Depends(get_bot_runner)]
