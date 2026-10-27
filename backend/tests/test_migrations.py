import os
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect

from app.core.config import settings


def test_alembic_migrations():
    """Verify that Alembic migrations run cleanly to head on a clean database."""
    test_db_file = "test_migration_run.db"
    if os.path.exists(test_db_file):
        os.remove(test_db_file)

    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ini_path = os.path.join(base_dir, "alembic.ini")
        migrations_dir = os.path.join(base_dir, "migrations")

        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option("script_location", migrations_dir)
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{test_db_file}")

        # Upgrade to head
        command.upgrade(alembic_cfg, "head")


        # Inspect created tables
        engine = create_engine(f"sqlite:///{test_db_file}")
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        expected_tables = {
            "users",
            "community_reports",
            "saved_journeys",
            "journey_history",
            "saved_places",
            "trusted_contacts",
            "journey_shares",
            "arrival_confirmations",
            "evidence_sources",
            "street_segments",
            "audit_logs",
            "system_settings",
            "password_reset_tokens",
            "feedback",
            "evidence_observations"
        }
        for t in expected_tables:
            assert t in tables, f"Expected table '{t}' was not created by migrations."


        # Downgrade to base
        command.downgrade(alembic_cfg, "base")
        inspector_after = inspect(engine)
        remaining_tables = [t for t in inspector_after.get_table_names() if t != "alembic_version"]
        assert len(remaining_tables) == 0, f"Tables remained after downgrade: {remaining_tables}"

    finally:
        if os.path.exists(test_db_file):
            os.remove(test_db_file)
