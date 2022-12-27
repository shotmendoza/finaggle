"""Utils to scrape an initial ticker dataset."""

import logging
import sys

from . import scrape

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | finagg.indices.install - %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def run() -> None:
    """Initialize a local SQL table with popular ticker info."""
    c = scrape.run(djia=True, sp500=True, nasdaq100=True, drop_tables=True)
    logger.info(f"{sum(c.values())} rows written")
    logger.info("Installation complete!")