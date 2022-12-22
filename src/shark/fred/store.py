"""SQLAlchemy interfaces for mixed features."""

import os
import pathlib

from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect
from sqlalchemy.engine import Engine, Inspector

_DATABASE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "fred_features.sqlite"
)

_DATABASE_URL = os.environ.get(
    "FRED_FEATURES_DATABASE_URL",
    f"sqlite:///{_DATABASE_PATH}",
)


def define_db(
    url: str = _DATABASE_URL,
) -> tuple[tuple[Engine, MetaData], Inspector, tuple[Table, ...]]:
    """Utility method for defining the SQLAlchemy elements.

    Used for the main SQL tables and for creating test
    databases.

    Args:
        url: SQLAlchemy database URL.
        path: Path to database file.

    Returns:
        The engine, engine inspector, metadata, and tables associated with
        the database definition.

    """
    engine = create_engine(url)
    inspector: Inspector = inspect(engine)
    metadata = MetaData()
    if inspector.has_table("economic_features"):
        economic_features = Table(
            "economic_features",
            metadata,
            Column(
                "date",
                String,
                primary_key=True,
                doc="Economic data series release date.",
            ),
            autoload_with=engine,
        )
    else:
        economic_features = None
    return (engine, metadata), inspector, (economic_features,)


(engine, metadata), inspector, (economic_features,) = define_db()