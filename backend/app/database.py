import logging
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import DateTime, TypeDecorator, create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

logger = logging.getLogger("sams")


class Base(DeclarativeBase):
    pass


class TZDateTime(TypeDecorator):
    """timestamptz on Postgres, naive UTC on SQLite, always tz-aware in Python."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _records):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    return create_engine(
        url,
        future=True,
        pool_pre_ping=True,
        connect_args={"prepare_threshold": None},
    )


engine = build_engine(settings.resolved_database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def prepare_database() -> None:
    import app.models  # noqa: F401


    if settings.is_sqlite:
        settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(engine)
        return

    tables = set(inspect(engine).get_table_names(schema="public"))
    if "users" in tables:
        return

    if settings.supabase_url:
        raise RuntimeError(
            "This Supabase project has no tables yet. Run supabase/schema.sql in the "
            "Supabase SQL editor, then start the API again."
        )

    Base.metadata.create_all(engine)
    logger.info("Created the database schema automatically (no existing tables were found).")


def ping() -> bool:
    with engine.connect() as connection:
        connection.execute(text("select 1"))
    return True
