import src.finagg


def test_get() -> None:
    src.finagg.yfinance.api.get("AAPL")
