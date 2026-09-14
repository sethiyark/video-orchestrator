"""Run with python -m app.database to apply migrations and import legacy state."""

from .config import Settings
from .store import Store

if __name__ == "__main__":
    store = Store(Settings().database_url)
    print(f"Database ready: {store.engine.dialect.name}; {len(store.list())} videos")
    store.engine.dispose()
