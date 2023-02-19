"""Features from SEC sources."""

import multiprocessing as mp
from functools import cache
from typing import Literal

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from tqdm import tqdm

from .. import backend, utils
from . import api, sql


def _install_quarterly_features(ticker: str, /) -> int:
    """Helper for creating and inserting data into the SEC quarterly
    features table from the raw data table.

    This function is used within a multiprocessing pool. No data
    is inserted if no feature rows can be constructed from the raw
    data table.

    Args:
        ticker: Ticker to create features for and insert.

    """
    df = QuarterlyFeatures.from_sql(ticker)
    rowcount = len(df.index)
    if not rowcount:
        return 0
    QuarterlyFeatures.to_store(ticker, df)
    return rowcount


def _install_relative_quarterly_features(ticker: str, /) -> int:
    """Helper for creating and inserting data into the SEC relative
    quarterly features table from the quarterly and industry quarterly
    features.

    Args:
        ticker: Ticker to create features for and insert.

    """
    df = RelativeQuarterlyFeatures.from_other_store(ticker)
    rowcount = len(df.index)
    if not rowcount:
        return 0
    RelativeQuarterlyFeatures.to_store(ticker, df)
    return rowcount


def get_unique_filings(
    df: pd.DataFrame, /, *, form: str = "10-Q", units: None | str = None
) -> pd.DataFrame:
    """Get all unique rows as determined by the filing date
    and tag for a period.

    Args:
        df: Dataframe without unique rows.
        form: Only keep rows with form type `form`.
        units: Only keep rows with units `units` if not `None`.

    Returns:
        Dataframe with unique rows.

    """
    mask = df["form"] == form
    match form:
        case "10-K":
            mask &= df["fp"] == "FY"
        case "10-Q":
            mask &= df["fp"].str.startswith("Q")
    if units:
        mask &= df["units"] == units
    df = df[mask]
    return (
        df.sort_values(["fy", "fp", "filed"])
        .groupby(["fy", "fp", "tag"], as_index=False)
        .first()
    )


class IndustryQuarterlyFeatures:
    """Methods for gathering industry-averaged quarterly data from SEC
    features.

    """

    @classmethod
    def from_store(
        cls,
        /,
        *,
        ticker: None | str = None,
        code: None | str = None,
        level: Literal[2, 3, 4] = 2,
        start: str = "0000-00-00",
        end: str = "9999-99-99",
        engine: Engine = backend.engine,
    ) -> pd.DataFrame:
        """Get quarterly features from the feature store,
        aggregated for an entire industry.

        The industry can be chosen according to a company or
        by an industry code directly. If a company is provided,
        then the first `level` digits of the company's SIC code
        is used for the industry code.

        Args:
            ticker: Company ticker. Lookup the industry associated
                with this company. Mutually exclusive with `code`.
            code: Industry SIC code to use for industry lookup.
                Mutually exclusive with `ticker`.
            level: Industry level to aggregate features at.
                The industry used according to `ticker` or `code`
                is subsampled according to this value. Options include:
                    2 = major group (e.g., furniture and fixtures)
                    3 = industry group (e.g., office furnitures)
                    4 = industry (e.g., wood office furniture)
            start: The start date of the observation period.
            end: The end date of the observation period.
            engine: Raw data and feature data SQL database engine.

        Returns:
            Quarterly data dataframe with each tag as a
            separate column. Sorted by filing date.

        Raises:
            ValueError if neither a `ticker` nor `code` are provided.

        """
        with engine.begin() as conn:
            if ticker:
                row = conn.execute(
                    sa.select(sql.submissions.c.sic)
                    .distinct()
                    .where(sql.submissions.c.cik == api.get_cik(ticker))
                )
                ((sic,),) = row
                code = str(sic)[:level]
            elif code:
                code = code[:level]
            else:
                raise ValueError("Must provide a `ticker` or `code`.")

            stmt = (
                sa.select(
                    sql.quarterly_features.c.fy,
                    sql.quarterly_features.c.fp,
                    sa.func.max(sql.quarterly_features.c.filed).label("filed"),
                    sql.quarterly_features.c.name,
                    sa.func.avg(sql.quarterly_features.c.value).label("avg"),
                    sa.func.std(sql.quarterly_features.c.value).label("std"),
                )
                .join(
                    sql.submissions,
                    (sql.submissions.c.cik == sql.quarterly_features.c.cik)
                    & (sql.submissions.c.sic.startswith(code)),
                )
                .group_by(
                    sql.quarterly_features.c.fy,
                    sql.quarterly_features.c.fp,
                    sql.quarterly_features.c.name,
                )
            )
            df = pd.DataFrame(
                conn.execute(
                    stmt.where(
                        sql.quarterly_features.c.filed >= start,
                        sql.quarterly_features.c.filed <= end,
                    )
                )
            )
        df = df.pivot(
            index=["fy", "fp", "filed"], values=["avg", "std"], columns="name"
        ).sort_index()
        return df


class QuarterlyFeatures:
    """Quarterly features from SEC EDGAR data."""

    #: Columns within this feature set.
    columns = (
        "AssetsCurrent_pct_change",
        "DebtEquityRatio",
        "EarningsPerShare",
        "InventoryNet_pct_change",
        "LiabilitiesCurrent_pct_change",
        "NetIncomeLoss_pct_change",
        "OperatingIncomeLoss_pct_change",
        "PriceBookRatio",
        "QuickRatio",
        "ReturnOnEquity",
        "StockholdersEquity_pct_change",
        "WorkingCapitalRatio",
    )

    #: XBRL disclosure concepts to pull for a company.
    concepts: tuple[api.Concept, ...] = (
        {"tag": "AssetsCurrent", "taxonomy": "us-gaap", "units": "USD"},
        {
            "tag": "EarningsPerShareBasic",
            "taxonomy": "us-gaap",
            "units": "USD/shares",
        },
        {"tag": "InventoryNet", "taxonomy": "us-gaap", "units": "USD"},
        {"tag": "LiabilitiesCurrent", "taxonomy": "us-gaap", "units": "USD"},
        {"tag": "NetIncomeLoss", "taxonomy": "us-gaap", "units": "USD"},
        {"tag": "OperatingIncomeLoss", "taxonomy": "us-gaap", "units": "USD"},
        {"tag": "StockholdersEquity", "taxonomy": "us-gaap", "units": "USD"},
    )

    #: Columns that're replaced with their respective percent changes.
    pct_change_columns = (
        "AssetsCurrent",
        "InventoryNet",
        "LiabilitiesCurrent",
        "NetIncomeLoss",
        "OperatingIncomeLoss",
        "StockholdersEquity",
    )

    @classmethod
    def _normalize(cls, df: pd.DataFrame, /) -> pd.DataFrame:
        """Normalize quarterly features columns."""
        df = df.set_index(["fy", "fp"])
        df["filed"] = df.groupby(["fy", "fp"])["filed"].max()
        df = df.reset_index()
        df = (
            df.pivot(index=["fy", "fp", "filed"], values="value", columns="tag")
            .astype(float)
            .sort_index()
        )
        df["EarningsPerShare"] = df["EarningsPerShareBasic"]
        df["DebtEquityRatio"] = df["LiabilitiesCurrent"] / df["StockholdersEquity"]
        df["PriceBookRatio"] = df["StockholdersEquity"] / (
            df["AssetsCurrent"] - df["LiabilitiesCurrent"]
        )
        df["QuickRatio"] = (df["AssetsCurrent"] - df["InventoryNet"]) / df[
            "LiabilitiesCurrent"
        ]
        df["ReturnOnEquity"] = df["NetIncomeLoss"] / df["StockholdersEquity"]
        df["WorkingCapitalRatio"] = df["AssetsCurrent"] / df["LiabilitiesCurrent"]
        df = utils.quantile_clip(df)
        pct_change_columns = [f"{col}_pct_change" for col in cls.pct_change_columns]
        df[pct_change_columns] = df[list(cls.pct_change_columns)].apply(
            utils.safe_pct_change
        )
        df.columns = df.columns.rename(None)
        df = df[list(cls.columns)]
        return df.dropna()

    @classmethod
    def from_api(
        cls, ticker: str, /, *, start: str = "0000-00-00", end: str = "9999-99-99"
    ) -> pd.DataFrame:
        """Get quarterly features directly from the SEC API.

        Not all data series are published at the same rate or
        time. Missing rows for less-frequent quarterly publications
        are forward filled.

        Args:
            ticker: Company ticker.
            start: The start date of the observation period.
            end: The end date of the observation period.

        Returns:
            Quarterly data dataframe with each tag as a
            separate column. Sorted by filing date.

        """
        dfs = []
        for concept in cls.concepts:
            tag = concept["tag"]
            taxonomy = concept["taxonomy"]
            units = concept["units"]
            df = api.company_concept.get(
                tag, ticker=ticker, taxonomy=taxonomy, units=units
            )
            df = get_unique_filings(df, units=units)
            df = df[(df["filed"] >= start) & (df["filed"] <= end)]
            dfs.append(df)
        df = pd.concat(dfs)
        return cls._normalize(df)

    @classmethod
    def from_sql(
        cls,
        ticker: str,
        /,
        *,
        start: str = "0000-00-00",
        end: str = "9999-99-99",
        engine: Engine = backend.engine,
    ) -> pd.DataFrame:
        """Get quarterly features from a local SEC SQL table.

        Not all data series are published at the same rate or
        time. Missing rows for less-frequent quarterly publications
        are forward filled.

        Args:
            ticker: Company ticker.
            start: The start date of the observation period.
            end: The end date of the observation period.
            engine: Raw store database engine.

        Returns:
            Quarterly data dataframe with each tag as a
            separate column. Sorted by filing date.

        """
        with engine.begin() as conn:
            df = pd.DataFrame(
                conn.execute(
                    sql.tags.select().where(
                        sql.tags.c.cik == api.get_cik(ticker),
                        sql.tags.c.tag.in_(
                            [concept["tag"] for concept in cls.concepts]
                        ),
                        sql.tags.c.filed >= start,
                        sql.tags.c.filed <= end,
                    )
                )
            )
        return cls._normalize(df)

    @classmethod
    def from_store(
        cls,
        ticker: str,
        /,
        *,
        start: str = "0000-00-00",
        end: str = "9999-99-99",
        engine: Engine = backend.engine,
    ) -> pd.DataFrame:
        """Get features from the features SQL table.

        This is the preferred method for accessing features for
        offline analysis (assuming data in the local SQL table
        is current).

        Args:
            ticker: Company ticker.
            start: The start date of the observation period.
            end: The end date of the observation period.
            engine: Feature store database engine.

        Returns:
            Quarterly data dataframe with each tag as a
            separate column. Sorted by filing date.

        """
        cik = api.get_cik(ticker)
        with engine.begin() as conn:
            df = pd.DataFrame(
                conn.execute(
                    sql.quarterly_features.select().where(
                        sql.quarterly_features.c.cik == cik,
                        sql.quarterly_features.c.filed >= start,
                        sql.quarterly_features.c.filed <= end,
                    )
                )
            )
        df = df.pivot(
            index=["fy", "fp", "filed"], values="value", columns="name"
        ).sort_index()
        df.columns = df.columns.rename(None)
        df = df[list(cls.columns)]
        return df

    @classmethod
    @cache
    def get_candidate_ticker_set(
        cls,
        lb: int = 1,
    ) -> set[str]:
        """Get all unique tickers in the raw SQL table that MAY BE ELIGIBLE
        to be in the feature's SQL table.

        Args:
            lb: Minimum number of rows required to include a ticker in the
                returned set.

        Returns:
            All unique tickers that're valid for creating quarterly features
            that also have at least `lb` rows for each tag used for
            constructing the features.

        """
        with backend.engine.begin() as conn:
            tickers = set()
            for row in conn.execute(
                sa.select(
                    sql.tags.c.cik,
                    *[
                        sa.func.sum(
                            sa.case({concept["tag"]: 1}, value=sql.tags.c.tag, else_=0)
                        ).label(concept["tag"])
                        for concept in cls.concepts
                    ],
                )
                .distinct()
                .group_by(sql.tags.c.cik)
                .having(
                    *[sa.text(f"{concept['tag']} >= {lb}") for concept in cls.concepts]
                )
            ):
                cik = row[0]
                ticker = api.get_ticker(str(cik))
                tickers.add(ticker)
        return tickers

    @classmethod
    @cache
    def get_ticker_set(
        cls,
        lb: int = 1,
    ) -> set[str]:
        """Get all unique tickers in the feature's SQL table.

        Args:
            lb: Minimum number of rows required to include a ticker in the
                returned set.

        Returns:
            All unique tickers that contain all the columns for creating
            quarterly features that also have at least `lb` rows.

        """
        with backend.engine.begin() as conn:
            tickers = set()
            for cik in conn.execute(
                sa.select(sql.quarterly_features.c.cik)
                .distinct()
                .group_by(sql.quarterly_features.c.cik)
                .having(
                    *[
                        sa.func.count(sql.quarterly_features.c.name == col) >= lb
                        for col in cls.columns
                    ]
                )
            ):
                (cik,) = cik
                ticker = api.get_ticker(str(cik))
                tickers.add(ticker)
        return tickers

    @classmethod
    def install(cls, *, processes: int = mp.cpu_count() - 1) -> int:
        """Drop the feature's table, create a new one, and insert data
        transformed from another raw SQL table.

        Args:
            processes: Number of background processes to use for installation.

        Returns:
            Number of rows written to the feature's SQL table.

        """
        sql.quarterly_features.drop(backend.engine, checkfirst=True)
        sql.quarterly_features.create(backend.engine)

        tickers = cls.get_candidate_ticker_set()
        total_rows = 0
        with tqdm(
            total=len(tickers),
            desc="Installing SEC quarterly features",
            position=0,
            leave=True,
        ) as pbar:
            with mp.Pool(
                processes=processes, initializer=backend.engine.dispose
            ) as pool:
                for rows in pool.imap_unordered(_install_quarterly_features, tickers):
                    pbar.update()
                    total_rows += rows
        return total_rows

    @classmethod
    def to_store(
        cls,
        ticker: str,
        df: pd.DataFrame,
        /,
        *,
        engine: Engine = backend.engine,
    ) -> int:
        """Write the dataframe to the feature store for `ticker`.

        Args:
            ticker: Company ticker.
            df: Dataframe to store completely as rows in a local SQL
                table.
            engine: Feature store database engine.

        Returns:
            Number of rows written to the SQL table.

        """
        df = df.reset_index(names=["fy", "fp", "filed"])
        df = df.melt(["fy", "fp", "filed"], var_name="name", value_name="value")
        df["cik"] = api.get_cik(ticker)
        with engine.begin() as conn:
            conn.execute(sql.quarterly_features.insert(), df.to_dict(orient="records"))  # type: ignore[arg-type]
        return len(df.index)


class RelativeQuarterlyFeatures:
    """Quarterly features from SEC EDGAR data normalized according to industry
    averages and standard deviations.

    """

    #: Columns within this feature set.
    columns = (
        "AssetsCurrent_pct_change",
        "DebtEquityRatio",
        "EarningsPerShare",
        "InventoryNet_pct_change",
        "LiabilitiesCurrent_pct_change",
        "NetIncomeLoss_pct_change",
        "OperatingIncomeLoss_pct_change",
        "PriceBookRatio",
        "QuickRatio",
        "ReturnOnEquity",
        "StockholdersEquity_pct_change",
        "WorkingCapitalRatio",
    )

    @classmethod
    def from_other_store(
        cls,
        ticker: str,
        /,
        *,
        level: Literal[2, 3, 4] = 2,
        start: str = "0000-00-00",
        end: str = "9999-99-99",
        engine: Engine = backend.engine,
    ) -> pd.DataFrame:
        """Get features from other features SQL table.

        Args:
            ticker: Company ticker.
            level: Industry level to aggregate relative features at.
                The industry used according to `ticker` is subsampled
                according to this value. Options include:
                    2 = major group (e.g., furniture and fixtures)
                    3 = industry group (e.g., office furnitures)
                    4 = industry (e.g., wood office furniture)
            start: The start date of the observation period.
            end: The end date of the observation period.
            engine: Feature store database engine.

        Returns:
            Relative quarterly data dataframe with each tag as a
            separate column. Sorted by filing date.

        """
        company_df = QuarterlyFeatures.from_store(
            ticker, start=start, end=end, engine=engine
        ).reset_index(["filed"])
        filed = company_df["filed"]
        industry_df = IndustryQuarterlyFeatures.from_store(
            ticker=ticker, level=level, start=start, end=end, engine=engine
        ).reset_index(["filed"])
        company_df = (company_df - industry_df["avg"]) / industry_df["std"]
        company_df["filed"] = filed
        return (
            company_df.fillna(method="ffill")
            .dropna()
            .reset_index()
            .drop_duplicates("filed")
            .set_index(["fy", "fp", "filed"])
        )

    @classmethod
    def from_store(
        cls,
        ticker: str,
        /,
        *,
        start: str = "0000-00-00",
        end: str = "9999-99-99",
        engine: Engine = backend.engine,
    ) -> pd.DataFrame:
        """Get features from the features SQL table.

        This is the preferred method for accessing features for
        offline analysis (assuming data in the local SQL table
        is current).

        Args:
            ticker: Company ticker.
            start: The start date of the observation period.
            end: The end date of the observation period.
            engine: Feature store database engine.

        Returns:
            Quarterly data dataframe with each tag as a
            separate column. Sorted by filing date.

        """
        cik = api.get_cik(ticker)
        with engine.begin() as conn:
            df = pd.DataFrame(
                conn.execute(
                    sql.relative_quarterly_features.select().where(
                        sql.relative_quarterly_features.c.cik == cik,
                        sql.relative_quarterly_features.c.filed >= start,
                        sql.relative_quarterly_features.c.filed <= end,
                    )
                )
            )
        df = df.pivot(
            index=["fy", "fp", "filed"], values="value", columns="name"
        ).sort_index()
        df.columns = df.columns.rename(None)
        df = df[list(cls.columns)]
        return df

    #: The candidate set is just the quarterly feature ticket set.
    get_candidate_ticker_set = QuarterlyFeatures.get_ticker_set

    @classmethod
    @cache
    def get_ticker_set(
        cls,
        lb: int = 1,
    ) -> set[str]:
        """Get all unique tickers in the feature's SQL table.

        Args:
            lb: Minimum number of rows required to include a ticker in the
                returned set.

        Returns:
            All unique tickers that contain all the columns for creating
            quarterly features that also have at least `lb` rows.

        """
        with backend.engine.begin() as conn:
            tickers = set()
            for cik in conn.execute(
                sa.select(sql.relative_quarterly_features.c.cik)
                .distinct()
                .group_by(sql.relative_quarterly_features.c.cik)
                .having(
                    *[
                        sa.func.count(sql.relative_quarterly_features.c.name == col)
                        >= lb
                        for col in cls.columns
                    ]
                )
            ):
                (cik,) = cik
                ticker = api.get_ticker(str(cik))
                tickers.add(ticker)
        return tickers

    @classmethod
    def install(cls, *, processes: int = mp.cpu_count() - 1) -> int:
        """Drop the feature's table, create a new one, and insert data
        transformed from another raw SQL table.

        Args:
            processes: Number of background processes to use for installation.

        Returns:
            Number of rows written to the feature's SQL table.

        """
        sql.relative_quarterly_features.drop(backend.engine, checkfirst=True)
        sql.relative_quarterly_features.create(backend.engine)

        tickers = cls.get_candidate_ticker_set()
        total_rows = 0
        with tqdm(
            total=len(tickers),
            desc="Installing SEC industry-relative quarterly features",
            position=0,
            leave=True,
        ) as pbar:
            with mp.Pool(
                processes=processes, initializer=backend.engine.dispose
            ) as pool:
                for rows in pool.imap_unordered(
                    _install_relative_quarterly_features, tickers
                ):
                    pbar.update()
                    total_rows += rows
        return total_rows

    @classmethod
    def to_store(
        cls,
        ticker: str,
        df: pd.DataFrame,
        /,
        *,
        engine: Engine = backend.engine,
    ) -> int:
        """Write the dataframe to the feature store for `ticker`.

        Args:
            ticker: Company ticker.
            df: Dataframe to store completely as rows in a local SQL
                table.
            engine: Feature store database engine.

        Returns:
            Number of rows written to the SQL table.

        """
        df = df.reset_index(names=["fy", "fp", "filed"])
        df = df.melt(["fy", "fp", "filed"], var_name="name", value_name="value")
        df["cik"] = api.get_cik(ticker)
        with engine.begin() as conn:
            conn.execute(sql.relative_quarterly_features.insert(), df.to_dict(orient="records"))  # type: ignore[arg-type]
        return len(df.index)


#: Public-facing API.
industry_quarterly = IndustryQuarterlyFeatures()
quarterly = QuarterlyFeatures()
relative_quarterly = RelativeQuarterlyFeatures()
