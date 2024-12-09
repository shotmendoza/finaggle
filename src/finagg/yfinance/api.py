"""Simple wrappers for Yahoo! Finance."""

import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def get(
    ticker: str,
    /,
    *,
    start: None | str = None,
    end: None | str = None,
    interval: str = "1d",
    period: str = "max",
    prepost: bool = False,
    actions: bool = False,
    auto_adjust: bool = True,
    back_adjust: bool = False,
    repair: bool = False,
    keepna: bool = False,
    proxy: str | None = None,
    rounding: bool = False,
    timeout: None | float = 10,
    raise_errors: bool = False
) -> pd.DataFrame:
    """Get a ticker's stock price (OHLCV) history.

    see: https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html

    Does a simple transform on Yahoo! Finance's ticker API dataframe result to
    be a bit more consistent with other API implementations.

    Updated the behavior for this function because I liked my functionality better
    for more customization. Combined the include date logic to keep consistency with the rest of the project.

    :param ticker: ticker symbol as a string
    :param period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y ,ytd, max. Use period parameter or use start and end
    :param interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo. Intraday cuts off after last 60d
    :param start: Download start date string (YYYY-MM-DD) or _datetime, inclusive. Default is 99 years ago
    :param end: see start. exclusive of date. E.g. for end='2023-01-01', the last data point will be on '2022-12-31'
    :param prepost: Include 'Pre' and 'Post' market data in results? Default is False
    :param actions:
    :param auto_adjust: Adjust all OHLC automatically? Default is True
    :param back_adjust: Back-adjusted data to mimic true historical prices
    :param repair: Detect currency unit 100x mixups and attempt repair. Default is False
    :param keepna: Keep NaN rows returned by Yahoo? Default is False
    :param proxy: Optional. Proxy server URL scheme. Default is None
    :param rounding: Round values to 2 decimal places? Optional. Default is False = precision suggested by Yahoo!
    :param timeout: If not None stops waiting for a response after given number of seconds
    :param raise_errors: If True, then raise errors as Exceptions instead of logging
    :return: Dataframe with OHLCV data from YahooFinance

    Args:
        ticker: Company ticker to get historical price data for.

        start: (YYYY-MM-DD) Start date for stock price history. Defaults to the first recorded date.

        end: (YYYY-MM-DD) End date for stock price history. Defaults to the last recorded date.

        interval: Frequency at which stock price history is grabbed.
            1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo.
            Intraday cuts off after last 60d

        period: Time period to get in the past. ``"max"`` returns the full
            stock price history and the default.

    Returns:
        Yahoo! Finance auto-adjusted stock price history with slightly
        different (more normalized) column names.

    Examples:
        >>> finagg.yfinance.api.get("AAPL").head(5)  # doctest: +SKIP
                 date    open    high     low   close     volume ticker
        0  1980-12-12  0.0997  0.1002  0.0997  0.0997  469033600   AAPL
        1  1980-12-15  0.0950  0.0950  0.0945  0.0945  175884800   AAPL
        2  1980-12-16  0.0880  0.0880  0.0876  0.0876  105728000   AAPL
        3  1980-12-17  0.0897  0.0902  0.0897  0.0897   86441600   AAPL
        4  1980-12-18  0.0924  0.0928  0.0924  0.0924   73449600   AAPL

    """
    # yfinance returns data exclusive of the end date if provided,
    # so we add an extra day to be consistent across all other
    # methods that're inclusive of the end date.
    if end is not None:
        end_plus_one = datetime.fromisoformat(end) + timedelta(days=1)
        end = end_plus_one.strftime("%Y-%m-%d")

    stock = yf.Ticker(ticker)
    df = stock.history(
        period=period, interval=interval, start=start, end=end,
        prepost=prepost, actions=actions, auto_adjust=auto_adjust,
        back_adjust=back_adjust, repair=repair, keepna=keepna,
        proxy=proxy, rounding=rounding, timeout=timeout, raise_errors=raise_errors
    )
    df.index = pd.to_datetime(df.index).date.astype(str)
    df = df.rename_axis("date").reset_index()
    df["ticker"] = stock.ticker
    df = df.drop(columns=["Dividends", "Stock Splits"], errors="ignore")
    df.columns = map(str.lower, df.columns)
    return df  # type: ignore[no-any-return]
