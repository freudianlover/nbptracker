import json
import pytest
from src.extract.nbp import NbpClient
from pathlib import Path

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
