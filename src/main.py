# orchestration script

from dotenv import load_dotenv
import os
from src.load.postgres import PostgresLoader
from src.extract.nbp import NbpClient
import psycopg2
import sys
from datetime import date
import structlog
from src.extract.exceptions import NbpApiError
from src.extract.models import ExchangeRate
from src.load.exceptions import PostgresError
from src.loger import configure_logger


load_dotenv()
configure_logger()
log = structlog.get_logger()


pg_host = os.getenv("POSTGRES_HOST")
pg_port = os.getenv("POSTGRES_PORT")
pg_db = os.getenv("POSTGRES_DB")
pg_user = os.getenv("POSTGRES_USER")
pg_password = os.getenv("POSTGRES_PASSWORD")


def get_tracked_currencies(conn) -> set[str]:
    """
    Read list of active currency codes from `currencies` table.

    Returns:
        Set of 3-letter ISO codes, e.g. {'USD', 'EUR', 'JPY'}
    """
    currency_codes = set()

    with conn.cursor() as cur:
        cur.execute("SELECT code FROM currencies WHERE active = TRUE;")
        results = cur.fetchall()

        for row in results:
            currency_codes.add(row[0])
    return currency_codes


def filter_tracked_rates(
    rates: list[ExchangeRate],
    tracked_codes: set[str],
) -> list[ExchangeRate]:
    """Filter rates to only currencies in tracked_codes."""
    tracked_rates = []
    for rate in rates:
        if rate.currency_code in tracked_codes:
            tracked_rates.append(rate)
    filtered_number = len(rates) - len(tracked_rates)
    log.info("Untracked rates have been filtered out",
             filtered_out=filtered_number)
    return tracked_rates


def main() -> int:
    """
    Main pipeline.

    Returns:
        Exit code: 0 = success, 1 = failure
    """
    user_agent = os.getenv("NBP_USER_AGENT", "nbptracker/0.1")
    log.info("pipeline_started", date=date.today().isoformat())

    try:
        client = NbpClient(user_agent=user_agent)
        loader = PostgresLoader()

        with loader.connection() as conn:
            tracked = get_tracked_currencies(conn)
            log.info("tracked_loaded", count=len(
                tracked), codes=sorted(tracked))
            rates = client.fetch_table_a()
            filtered = filter_tracked_rates(rates, tracked)
            if not filtered:
                log.warning(...)
                return 0
            inserted, updated = loader.upsert_rates(conn, filtered)
            log.info("pipeline_complete", inserted=inserted, updated=updated)
            return 0

    except NbpApiError as e:
        log.error("nbp_failure", error=str(e))
        return 1
    except PostgresError as e:
        log.error("postgres_failure", error=str(e))
        return 1
    except Exception as e:
        log.exception("unexpected_error", error=str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
