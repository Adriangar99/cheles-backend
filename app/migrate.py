"""Brings the database schema to the latest Alembic revision (run on every container start)."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db import engine

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "0001_baseline"


def _config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return config


def migrate() -> None:
    """Upgrades to head, first adopting a database created by the old create_all startup as the baseline."""
    config = _config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if "alembic_version" not in tables and "users" in tables:
            # The old startup built exactly the baseline schema: record it, change nothing
            print(f"Existing database without schema version: stamping it as {BASELINE}")
            command.stamp(config, BASELINE)
        command.upgrade(config, "head")
