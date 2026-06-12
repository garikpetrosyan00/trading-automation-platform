from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.execution_reconciliation_worker_status import ExecutionReconciliationWorkerStatus


class ExecutionReconciliationWorkerStatusRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_worker_name(self, worker_name: str) -> ExecutionReconciliationWorkerStatus | None:
        return self.db.scalar(
            select(ExecutionReconciliationWorkerStatus).where(
                ExecutionReconciliationWorkerStatus.worker_name == worker_name
            )
        )

    def get_or_create(self, worker_name: str) -> ExecutionReconciliationWorkerStatus:
        status = self.get_by_worker_name(worker_name)
        if status is not None:
            return status
        status = ExecutionReconciliationWorkerStatus(worker_name=worker_name, state="stopped")
        self.db.add(status)
        self.db.flush()
        return status
