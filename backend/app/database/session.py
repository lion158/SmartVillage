"""Database engine and session lifecycle."""

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = BACKEND_DIR / "data" / "smart_village.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DATABASE_PATH}"


def get_database_url() -> str:
    """Return the configured database URL or the local SQLite default."""

    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create an engine with SQLite-specific safety settings when required."""

    url = database_url or get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    database_engine = create_engine(url, connect_args=connect_args)

    if url.startswith("sqlite"):

        @event.listens_for(database_engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return database_engine


DEFAULT_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Provide one SQLAlchemy session for a FastAPI request."""

    with SessionLocal() as session:
        yield session
