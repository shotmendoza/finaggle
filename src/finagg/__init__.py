"""Main package interface."""
from . import backend, bea, fred, fundam, indices, sec, testing, utils, yfinance

from importlib.metadata import PackageNotFoundError, version

from dotenv import load_dotenv

load_dotenv()


try:
    __version__ = version("finagg")
except PackageNotFoundError:
    pass
