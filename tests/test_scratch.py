from datetime import date
from pathlib import Path
from pprint import pprint
from time import sleep

from src import finagg


class TestDocumentsAvailable:
    def test_getting_sp500_index_underlying(self):
        """small interactive test to check how to get the financial
        statements for underlying stocks in the SP500

        Returns:

        """
        # (1) grabs S&P500 stocks and tickers
        sp500 = finagg.indices.api.sp500.get_ticker_list()
        example_set = sp500[:2]

        # (2) get financial statements on the 5 stocks
        x = finagg.sec.api.submissions.get(ticker=example_set[0])
        print(x)

        # (2a) company concepts
        df_2a = finagg.sec.api.company_concept.get(
            "EarningsPerShareBasic",
            ticker=example_set[0],
        )

        # (2b) company facts
        df_2b = finagg.sec.api.company_facts.get(ticker=example_set[0])
        df_2b = finagg.sec.api.filter_original_filings(df_2b, form="10-q")

        # (3) Printing out the financial dataset
        print(
            """
            #################################
            # PRINTING COMPANY FACTS
            #################################
            """
        )
        print(df_2b.info())
        print(df_2b.head(2))

        folder = Path("/Volumes/Sho's SSD/trading")
        ten_q = finagg.sec.api.group_and_pivot_filings(df_2b, form="10-Q")
        ten_q.to_csv(folder / f"ten_q {example_set[0]} - {date.today()}.csv")
        print(ten_q.info())
        print(ten_q.head(2))

        print(
            """
            #################################
            # PRINTING COMPANY FACTS
            #################################
            """
        )
        print()
        print("---")
        print(df_2a.info())
        print(df_2a.head(2))
