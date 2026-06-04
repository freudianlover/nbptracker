import requests
import json
import pandas as pd
from datetime import date, timedelta
from typing import Optional
from decimal import Decimal
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import structlog
from src.extract.exceptions import NbpApiError, NbpApiUnavailable, RateNotAvailable
from src.extract.models import ExchangeRate, from_nbp_json

log = structlog.get_logger()


class NbpClient:
    """
    to fill later
    """

    BASE_URL = "https://api.nbp.pl/api/exchangerates"

    def __init__(self,
                 user_agent: str,
                 timeout_seconds: int = 10,
                 session: Optional[requests.Session] = None,
                 ):
        self.timeout = timeout_seconds
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        """
        to fill later
        """
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(NbpApiUnavailable),
        reraise=True
    )
    def _get(self, endpoint: str) -> dict | list:
        log.info("nbp_request", endpoint=endpoint)
        url = f"{self.BASE_URL}{endpoint}?format=json"
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            log.warning("nbp_network_error", endpoint=endpoint, error=str(e))
            raise NbpApiUnavailable(
                "Network error fetching from NBP"
            ) from e
        status_code = response.status_code
        if status_code == 200:
            log.debug("nbp_response_ok", endpoint=endpoint, status=200)
            return response.json()
        elif status_code == 404:
            log.info("nbp_rate_not_available", endpoint=endpoint)
            raise RateNotAvailable(
                f"NBP returned status {status_code}, rate not available"
            )
        elif status_code >= 500:
            log.warning("nbp_unavailable", endpoint=endpoint,
                        status=status_code)
            raise NbpApiUnavailable(
                f"NBP returned status {status_code}"
            )
        else:
            log.error("nbp_unexpected_status",
                      endpoint=endpoint, status=status_code)
            raise NbpApiError(
                f"Unexpected status code: {status_code}")

    def fetch_table_a(self) -> list[ExchangeRate]:
        endpoint = "/tables/A/"
        try:
            data = self._get(endpoint)
        except RateNotAvailable:
            return []
        exchange_rates = []
        for item in data:
            for rate in item["rates"]:
                exchange_rates.append(ExchangeRate(
                    currency_code=rate["code"],
                    currency_name=rate["currency"],
                    effective_date=date.fromisoformat(item["effectiveDate"]),
                    rate_pln=Decimal(str(rate["mid"])),
                    table_no=item["no"],
                    table=item["table"]
                ))
                if not exchange_rates:
                    log.info("table_a_empty", endpoint=endpoint)
                    return []
        log.info("table_a_fetched",
                 date=..., count=len(exchange_rates), day=date.today().strftime("%A"))
        return exchange_rates

    def fetch_currency_history(self, currency_code: str, number_of_days: int) -> list[ExchangeRate]:
        endpoint = f"/rates/A/{currency_code}/last/{number_of_days}/"
        try:
            data = self._get(endpoint)
        except RateNotAvailable:
            return []
        fetched_history = []
        for rate in data["rates"]:
            fetched_history.append(from_nbp_json(data, rate))
        log.info("history_fetched", endpoint=endpoint, currency=currency_code,
                 days=number_of_days, count=len(fetched_history))
        return fetched_history

    def fetch_currency_period(self, currency_code: str, date_from: date, date_to: date) -> list[ExchangeRate]:
        """
        date_from - isoformat -> 2026-05-1
        date_to - isoformat -> 2026-05-29
        currency_code -> str of len(3)
        """
        endpoint = f"/rates/A/{currency_code}/{date_from}/{date_to}/"
        try:
            data = self._get(endpoint)
        except RateNotAvailable:
            return []
        fetched_period = []
        for rate in data["rates"]:
            fetched_period.append(from_nbp_json(data, rate))
        log.info("period_fetched", endpoint=endpoint, currency=currency_code,
                 date_from=date_from, date_to=date_to, count=len(fetched_period))
        return fetched_period
