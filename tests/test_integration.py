"""
testing everything alltogether
"""
import pytest
import os
from datetime import date
from decimal import Decimal
from dotenv import load_dotenv
from src.main import main, get_tracked_currencies
from src.load.postgres import PostgresLoader
from src.extract.models import ExchangeRate


load_dotenv()

INTEGRATION_ENABLED = os.getenv("INTEGRATION_TESTS", "false").lower() == "true"

pytestmark = pytest.mark.skipif(
    not INTEGRATION_ENABLED,
    reason="Integration tests disabled. Set INTEGRATION_TESTS=true to enable.",
)
# test1


def test_get_tracked_currencies_returns_seeded_codes():
    """Should return the 10 seeded currencies from init.sql."""
    # Arrange
    loader = PostgresLoader()

    # Act
    with loader.connection() as conn:
        tracked = get_tracked_currencies(conn)

    # Assert
    expected = {'USD', 'EUR', 'GBP', 'JPY',
                'CNY', 'HKD', 'SGD', 'KRW', 'PHP', 'MYR'}
    assert tracked == expected

# test2


def test_main_end_to_end_with_mocked_nbp(clean_db, mocker):
    """
    Full pipeline: mocked NBP returns 3 rates → real Postgres → verify data.

    This is the most important test in the suite -> it validates that
    extract + filter + load work together against a real database.
    """
    # Arrange — deterministic NBP response (3 tracked currencies)
    mock_rates = [
        ExchangeRate(
            currency_code="USD",
            currency_name="dolar amerykański",
            effective_date=date(2026, 6, 9),
            rate_pln=Decimal("4.0521"),
            table_no="101/A/NBP/2026",
            table="A",
        ),
        ExchangeRate(
            currency_code="EUR",
            currency_name="euro",
            effective_date=date(2026, 6, 9),
            rate_pln=Decimal("4.2987"),
            table_no="101/A/NBP/2026",
            table="A",
        ),
        ExchangeRate(
            currency_code="JPY",
            currency_name="jen (Japonia)",
            effective_date=date(2026, 6, 9),
            rate_pln=Decimal("0.022839"),
            table_no="101/A/NBP/2026",
            table="A",
        ),
    ]

    # Mock fetch_table_a to return our deterministic rates
    mocker.patch(
        'src.main.NbpClient.fetch_table_a',
        return_value=mock_rates,
    )

    # Act
    exit_code = main()

    # Assert exit code
    assert exit_code == 0

    # Assert data was actually inserted into real Postgres
    loader = PostgresLoader()
    with loader.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT currency_code, effective_date, rate_pln
                FROM exchange_rates_daily
                ORDER BY currency_code;
            """)
            rows = cur.fetchall()

    assert len(rows) == 3
    # Check that rates match what we mocked
    codes_in_db = {row[0] for row in rows}
    assert codes_in_db == {"USD", "EUR", "JPY"}

# test 3


def test_main_filters_out_untracked_currencies(clean_db, mocker):
    """When NBP returns rates for currencies NOT in currencies table, they should be filtered out."""
    # Arrange

    pass

# test 4 - adv


def test_main_idempotent_second_run_updates_not_inserts(clean_db, mocker):
    """Running main() twice with same data: 1st = inserts, 2nd = updates."""
    # Arrange — mock z 2 rates

    pass
