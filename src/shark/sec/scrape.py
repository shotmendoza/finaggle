"""Scrape the SEC API and store into local SQL tables."""

from typing import Sequence

from ..tickers import api as tickers_api
from . import api, features, sql


def run(
    tickers: str | Sequence[str],
    /,
    *,
    concepts: None | Sequence[dict[str, str]] = None,
) -> dict[str, int]:
    """Scrape company XBRL disclosures from the SEC API.

    ALL TABLES ARE DROPPED PRIOR TO SCRAPING!
    Scraped data is loaded into local SEC SQL tables.

    You can specify concepts by specifying tag-taxonomy
    pairs with the `concepts` arg or get all company concepts
    by leaving `concepts` as `None`

    Args:
        tickers: Company tickers to scrape.
        concepts: Taxonomy-tag pairs to scrape. If `None`,
            scrape all concepts.

    Returns:
        A dictionary mapping tickers to number of rows scraped
        for each ticker.

    """
    if isinstance(tickers, str):
        tickers = [tickers]

    updates = set()
    unique_tickers = set(tickers)
    for ticker in unique_tickers:
        match ticker.upper():
            case "DJIA":
                updates.update(tickers_api.djia.get_ticker_list())

            case "NASDAQ100":
                updates.update(tickers_api.nasdaq100.get_ticker_list())

            case "SP500":
                updates.update(tickers_api.sp500.get_ticker_list())
    unique_tickers |= updates

    sql.metadata.drop_all(sql.engine)
    sql.metadata.create_all(sql.engine)

    with sql.engine.connect() as conn:
        tickers_to_inserts = {}
        for ticker in unique_tickers:
            if concepts is None:
                df = api.company_facts.get(ticker=ticker)
                tickers_to_inserts[ticker] = len(df.index)
                conn.execute(sql.tags.insert(), df.to_dict(orient="records"))

            else:
                tickers_to_inserts[ticker] = 0
                for concept in concepts:
                    tag = concept.pop("tag")
                    taxonomy = concept.pop("taxonomy", "us-gaap")
                    units = concept.pop("units", "USD")
                    df = api.company_concept.get(
                        tag, ticker=ticker, taxonomy=taxonomy, units=units
                    )
                    df = features.get_unique_10q(df, units=units)
                    tickers_to_inserts[ticker] += len(df.index)
                    conn.execute(sql.tags.insert(), df.to_dict(orient="records"))
    return tickers_to_inserts
