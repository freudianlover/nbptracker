"""Database queries for Streamlit dashboard."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.load.postgres import PostgresLoader


@st.cache_data(ttl=60)
def get_active_currencies() -> list[str]:
    """Return list of active currency codes from DB."""
    loader = PostgresLoader()
    with loader.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT code FROM currencies WHERE active = TRUE ORDER BY code;")
            currency_list = cur.fetchall()
            return [row[0] for row in currency_list]


@st.cache_data(ttl=60)
def get_rates_for_period(
    currencies: tuple[str, ...],  # tuple, nie list! cache wymaga hashable
    from_date: date,
    to_date: date,
) -> pd.DataFrame:
    """
    Fetch rates for given currencies in date range.

    Returns DataFrame with columns: currency_code, effective_date, rate_pln, table_no
    """
    loader = PostgresLoader()
    with loader.connection() as conn:
        return pd.read_sql(
            """
            SELECT currency_code, effective_date, rate_pln, table_no
            FROM exchange_rates_daily
            WHERE currency_code = ANY(%(currencies)s)
              AND effective_date BETWEEN %(from_date)s AND %(to_date)s
            ORDER BY effective_date;
            """,
            conn,
            params={
                "currencies": list(currencies),
                "from_date": from_date,
                "to_date": to_date,
            },
        )


@st.cache_data(ttl=60)
def get_latest_rates(currencies: tuple[str, ...]) -> pd.DataFrame:
    """
    Get most recent rate per currency.

    Returns DataFrame with columns: currency_code, effective_date, rate_pln
    """
    loader = PostgresLoader()
    with loader.connection() as conn:
        return pd.read_sql(
            """
            SELECT DISTINCT ON (currency_code) 
                currency_code, effective_date, rate_pln
            FROM exchange_rates_daily
            WHERE currency_code = ANY(%(currencies)s)
            ORDER BY currency_code, effective_date DESC;
            """,
            conn,
            params={"currencies": list(currencies)},
        )


@st.cache_data(ttl=60)
def get_top_movers(currencies: tuple[str, ...], days: int = 7) -> pd.DataFrame:
    """
    For each currency, calculate % change over last N days.
    Returns DataFrame sorted by absolute % change (biggest movers first).
    """
    loader = PostgresLoader()
    with loader.connection() as conn:
        return pd.read_sql(
            """
            SELECT * FROM (
                WITH ranked AS (
                    SELECT 
                        currency_code,
                        effective_date,
                        rate_pln,
                        ROW_NUMBER() OVER (PARTITION BY currency_code ORDER BY effective_date DESC) as rn_latest,
                        ROW_NUMBER() OVER (PARTITION BY currency_code ORDER BY effective_date ASC) as rn_oldest
                    FROM exchange_rates_daily
                    WHERE currency_code = ANY(%(currencies)s)
                      AND effective_date >= CURRENT_DATE - %(days)s::int
                )
                SELECT 
                    currency_code,
                    MAX(CASE WHEN rn_oldest = 1 THEN rate_pln END) AS oldest_rate,
                    MAX(CASE WHEN rn_latest = 1 THEN rate_pln END) AS latest_rate,
                    ROUND(
                        (MAX(CASE WHEN rn_latest = 1 THEN rate_pln END) - 
                         MAX(CASE WHEN rn_oldest = 1 THEN rate_pln END)) 
                        / MAX(CASE WHEN rn_oldest = 1 THEN rate_pln END) * 100,
                        2
                    ) AS pct_change
                FROM ranked
                GROUP BY currency_code
            ) sub
            ORDER BY ABS(pct_change) DESC NULLS LAST;
            """,
            conn,
            params={"currencies": list(currencies), "days": days},
        )
