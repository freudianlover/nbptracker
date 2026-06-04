import requests


"""Custom exceptions for NBP API interactions."""


class NbpApiError(Exception):
    """Base class for any error with NBP API."""
    pass


class RateNotAvailable(NbpApiError):
    """
    NBP returned 404 — usually means weekend/holiday (no rate published).
    Not an actual error — caller should handle gracefully (skip & log).
    """
    pass


class NbpApiUnavailable(NbpApiError):
    """NBP API returned 5xx or network error. Retry-worthy."""
    pass
