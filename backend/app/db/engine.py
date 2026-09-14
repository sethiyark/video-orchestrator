from pathlib import Path

from sqlalchemy import create_engine, event


def make_engine(url):
    if "://" not in url:
        url = f"sqlite:///{Path(url).resolve()}"
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite") and not url.endswith(":memory:"):
        Path(url.split("///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False, "timeout": 10}
        if url.startswith("sqlite")
        else {},
    )
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def configure(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def migrate(engine):
    from alembic import command
    from alembic.config import Config

    # Register every mapped table on Base.metadata before upgrade.
    from . import jobs as _jobs  # noqa: F401
    from . import platform as _platform  # noqa: F401
    from . import series as _series  # noqa: F401

    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[2] / "migrations")
    )
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


__all__ = ["make_engine", "migrate"]
