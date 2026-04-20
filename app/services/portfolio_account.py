from app.core.logging import get_logger
from app.repositories.portfolio import PortfolioRepository

logger = get_logger(__name__)


class PortfolioAccountService:
    def __init__(self, repository: PortfolioRepository):
        self.repository = repository

    def ensure_account(self, base_currency: str, starting_cash):
        existing = self.repository.get_account()
        if existing is not None:
            logger.info(
                "portfolio_account_exists",
                extra={"base_currency": existing.base_currency, "account_id": existing.id},
            )
            return existing

        account = self.repository.create_account(base_currency=base_currency, starting_cash=starting_cash)
        logger.info(
            "portfolio_account_created",
            extra={"base_currency": account.base_currency, "account_id": account.id},
        )
        return account
