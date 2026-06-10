import json
import pytest
from src.extract.nbp import NbpClient
from pathlib import Path
from src.load.postgres import PostgresLoader

FIXTURES_DIR = Path("tests/fixtures")


def load_fixture(name: str) -> dict | list:
    """Load JSON file from tests/fixtures"""
    return json.loads((FIXTURES_DIR / name).read_text())


@pytest.fixture
def nbp_client():
    """Fixture przygotowujący instancję klienta do każdego testu."""
    return NbpClient(user_agent="TestAgent/1.0", timeout_seconds=5)


@pytest.fixture
def eur_range():
    return load_fixture("nbp_eur_range.json")


@pytest.fixture
def jpy_single():
    return load_fixture("nbp_jpy_single.json")


@pytest.fixture
def table_a():
    return load_fixture("nbp_table_a.json")


@pytest.fixture
def usd_last_10():
    return load_fixture("nbp_usd_last_10.json")


@pytest.fixture
def postgres_loader():
    """PostgresLoader with hardcoded DSN (no env var dependency in tests)."""
    return PostgresLoader(dsn="postgresql://test:test@localhost:5432/test")


@pytest.fixture
def sample_exchange_rates():
    """Sample list of ExchangeRate objects for testing upserts."""
    from datetime import date
    from decimal import Decimal
    from src.extract.models import ExchangeRate

    return [
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


@pytest.fixture
def clean_db():
    """
    Truncate exchange_rates_daily before and after each test.
    Ensures test isolation: each test starts with clean rates table.
    """
    loader = PostgresLoader()

    def _truncate():
        with loader.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "TRUNCATE TABLE exchange_rates_daily RESTART IDENTITY CASCADE;")
            conn.commit()

    _truncate()  # before
    yield
    _truncate()  # after
