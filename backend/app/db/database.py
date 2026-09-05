from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

DB_DIR = Path(__file__).resolve().parent


def default_database_url() -> str:
    return f"sqlite+aiosqlite:///{DB_DIR / 'codelens.db'}"


engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app.db import models  # noqa: F401

    DB_DIR.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_sqlite_columns)


def _migrate_sqlite_columns(connection) -> None:
    """Lightweight SQLite migrations for new production columns (dev/small deploys without Alembic)."""
    if "sqlite" not in str(settings.database_url):
        return
    cols = {
        "pr_reports": [
            ("installation_id", "INTEGER"),
            ("head_sha", "VARCHAR(64)"),
            ("source", "VARCHAR(32) DEFAULT 'oauth'"),
        ],
    }
    for table, definitions in cols.items():
        existing = {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()}
        for name, sql_type in definitions:
            if name not in existing:
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")
