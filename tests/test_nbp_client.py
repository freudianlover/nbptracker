from src.extract.nbp import NbpClient
from src.extract.exceptions import NbpApiUnavailable, NbpApiError, RateNotAvailable
import pytest
from unittest.mock import MagicMock
import requests
from decimal import Decimal
from datetime import date
from src.extract.models import ExchangeRate


def test_get_500_api_unavailable_retry(mocker, nbp_client):
    mocker.patch('time.sleep', return_value=None)

    mock_response = MagicMock()
    mock_response.status_code = 500

    mock_session_get = mocker.patch.object(
        nbp_client.session, 'get', return_value=mock_response)

    # Expecting final exception after 3 retries
    with pytest.raises(NbpApiUnavailable) as exc_info:
        nbp_client._get("/rates/a/eur")

    # Check whether the session was retried 3 times
    assert mock_session_get.call_count == 3
    assert "NBP returned status 500" in str(exc_info.value)

# test2


def test_fetch_currency_history_returns_exchange_rates(mocker, nbp_client, usd_last_10):
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = usd_last_10
    mocker.patch.object(nbp_client.session, 'get', return_value=mock_response)

    # Act
    rates = nbp_client.fetch_currency_history("USD", number_of_days=10)

    # Assert
    assert len(rates) == 10
    assert all(r.currency_code == "USD" for r in rates)
    assert isinstance(rates[0].rate_pln, Decimal)

# test3


def test_fetch_currency_history_returns_empty_on_404(mocker, nbp_client):
    # Arrange —> weekend simulation(404 return)
    mock_response = MagicMock()
    mock_response.status_code = 404
    mocker.patch.object(nbp_client.session, 'get', return_value=mock_response)

    # Act
    rates = nbp_client.fetch_currency_history("USD", number_of_days=10)

    # Assert,it should return a blank list
    assert rates == []

# test4


def test_get_retries_on_network_error_then_raises(mocker, nbp_client):
    # Arrange
    mocker.patch('time.sleep', return_value=None)  # speedup
    mocker.patch.object(
        nbp_client.session, 'get',
        side_effect=requests.ConnectionError("network down"),
    )

    # Act + Assert
    with pytest.raises(NbpApiUnavailable):
        nbp_client._get("/rates/A/USD/")


# test5
def test_fetch_table_a_parses_list_with_single_element(mocker, nbp_client, table_a):
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = table_a
    mocker.patch.object(nbp_client.session, 'get', return_value=mock_response)

    # Act
    rates = nbp_client.fetch_table_a()

    # Assert, table A ma ~35 walut
    assert len(rates) >= 30
    # Check whether all your target currencies were fetched
    codes = {r.currency_code for r in rates}
    assert "USD" in codes
    assert "EUR" in codes
    assert "JPY" in codes


# test6
def test_fetch_table_a_parses_list_with_single_element(mocker, nbp_client, table_a):
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = table_a
    mocker.patch.object(nbp_client.session, 'get', return_value=mock_response)

    # Act
    rates = nbp_client.fetch_table_a()

    # Assert, table A has about 35 currencies
    assert len(rates) >= 30
    # Check whether all the target currencies were fetched
    codes = {r.currency_code for r in rates}
    assert "USD" in codes
    assert "EUR" in codes
    assert "JPY" in codes
