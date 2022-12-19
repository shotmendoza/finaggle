"""Mixed feature SQLAlchemy interfaces."""

import os
import pathlib

from sqlalchemy import MetaData, create_engine

_SQL_DB_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "mixed.sqlite"
)

_SQL_DB_URL = os.environ.get(
    "MIXED_SQL_DB_URL",
    f"sqlite:///{_SQL_DB_PATH}",
)

#: SQLAlchemy engine used for all operations.
engine = create_engine(_SQL_DB_URL)

#: SQLAlchemy metadata used by all datasets.
metadata = MetaData()