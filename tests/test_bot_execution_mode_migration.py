import importlib.util
from pathlib import Path


def test_bot_execution_mode_migration_backfills_from_legacy_is_paper(monkeypatch) -> None:
    migration_path = Path(__file__).resolve().parents[1] / "alembic/versions/20260605_0026_add_bot_execution_mode.py"
    spec = importlib.util.spec_from_file_location("migration_20260605_0026", migration_path)
    assert spec is not None
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    calls: list[tuple[str, object]] = []

    class FakeOp:
        @staticmethod
        def add_column(*args, **kwargs):
            calls.append(("add_column", args))

        @staticmethod
        def execute(statement):
            calls.append(("execute", statement))

        @staticmethod
        def create_check_constraint(*args, **kwargs):
            calls.append(("create_check_constraint", args))

        @staticmethod
        def create_index(*args, **kwargs):
            calls.append(("create_index", args))

        @staticmethod
        def f(name):
            return name

    monkeypatch.setattr(migration, "op", FakeOp)

    migration.upgrade()

    executed_sql = [statement for name, statement in calls if name == "execute"]
    assert executed_sql == ["UPDATE bots SET execution_mode = CASE WHEN is_paper THEN 'paper' ELSE 'live' END"]
