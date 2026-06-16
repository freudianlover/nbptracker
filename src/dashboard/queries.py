"""Database queries for Streamlit dashboard."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.load.postgres import PostgresLoader
from decimal import Decimal
from typing import Literal


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
    currencies: tuple[str, ...],  # cache wymaga hashable
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


@st.cache_data(ttl=30)  # krótszy TTL bo użytkownik często edytuje
def get_alert_rules(active_only: bool = True) -> pd.DataFrame:
    """
    Fetch alert rules.

    Returns DataFrame with columns: id, currency_code, threshold_pln, operator, label, active, created_at
    """
    loader = PostgresLoader()
    with loader.connection() as conn:
        return pd.read_sql(
            """
            SELECT id, currency_code, threshold_pln, operator, label, active, created_at
            FROM alert_rules
            WHERE (NOT %(active_only)s) OR (active = TRUE)
            ORDER BY created_at DESC;
            """,
            conn,
            params={"active_only": active_only},
        )


def create_alert_rule(
    currency_code: str,
    threshold_pln: Decimal | float,
    operator: Literal["gt", "lt", "ge", "le"],
    label: str | None = None,
) -> int:
    """
    Insert new alert rule. Returns new rule_id.

    Args:
        currency_code: 3-letter ISO code (must exist in currencies table)
        threshold_pln: trigger value
        operator: gt/lt/ge/le (greater/less than, with/without equal)
        label: optional human-readable name

    Raises:
        psycopg2.errors.ForeignKeyViolation if currency_code doesn't exist
        psycopg2.errors.CheckViolation if operator is invalid
    """
    loader = PostgresLoader()
    with loader.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alert_rules (currency_code, threshold_pln, operator, label, active)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING id;
                """,
                (currency_code, threshold_pln, operator, label),
            )
            new_id = cur.fetchone()[0]
    # Invalidate cache so UI shows new rule
    get_alert_rules.clear()
    return new_id


def toggle_alert_rule(rule_id: int, active: bool) -> None:
    """Enable or disable a rule."""
    loader = PostgresLoader()
    with loader.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE alert_rules SET active = %s WHERE id = %s;",
                (active, rule_id),
            )
    get_alert_rules.clear()


@st.cache_data(ttl=30)
def get_alert_history(limit: int = 20) -> pd.DataFrame:
    """
    Fetch most recent triggered alerts joined with rule context.

    Returns DataFrame with columns: 
        rule_id, currency_code, operator, threshold_pln, label,
        rate_at_trigger, effective_date, triggered_at
    """
    loader = PostgresLoader()
    with loader.connection() as conn:
        return pd.read_sql(
            """
            SELECT 
                a.rule_id,
                r.currency_code,
                r.operator,
                r.threshold_pln,
                r.label,
                a.rate_at_trigger,
                a.effective_date,
                a.triggered_at
            FROM alerts_sent a
            JOIN alert_rules r ON r.id = a.rule_id
            ORDER BY a.triggered_at DESC
            LIMIT %(limit)s;
            """,
            conn,
            params={"limit": limit},
        )


def delete_alert_rule(rule_id: int) -> None:
    """Delete rule and its alert history (CASCADE)."""
    loader = PostgresLoader()
    with loader.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM alert_rules WHERE id = %s;",
                (rule_id,),
            )
    get_alert_rules.clear()
    get_alert_history.clear()
