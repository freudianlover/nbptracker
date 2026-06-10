"""PostgreSQL loader for exchange rates."""
import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import execute_values
import structlog

from src.extract.models import ExchangeRate
from src.load.exceptions import PostgresConnectionError
from datetime import datetime, timezone


log = structlog.get_logger()


class PostgresLoader:
    """
    Postgres loader for exchange_rates_daily table.

    Usage:
        loader = PostgresLoader()
        with loader.connection() as conn:
            inserted, updated = loader.upsert_rates(conn, rates)
    """

    UPSERT_SQL = """
        INSERT INTO exchange_rates_daily 
            (currency_code, effective_date, rate_pln, table_no, fetched_at)
        VALUES %s
        ON CONFLICT (currency_code, effective_date) 
        DO UPDATE SET 
            rate_pln = EXCLUDED.rate_pln,
            table_no = EXCLUDED.table_no,
            fetched_at = EXCLUDED.fetched_at
        RETURNING xmax = 0 AS inserted;
    """
    # xmax = 0 oznacza "to nowy wiersz" (insert). xmax > 0 to update.
    # RETURNING pozwala policzyć inserts vs updates.

    def __init__(self, dsn: str | None = None):
        """
        Args:
            dsn: Postgres connection string. Jeśli None, czytane z env vars 
                 (POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, etc.)
        """
        if dsn is None:
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            db = os.getenv("POSTGRES_DB")
            user = os.getenv("POSTGRES_USER")
            password = os.getenv("POSTGRES_PASSWORD")

            if not all([db, user, password]):
                raise PostgresConnectionError(
                    "Postgres credentails missing in env (POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)")

            dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        self.dsn = dsn

    @contextmanager
    def connection(self):
        """
        Context manager: zwraca psycopg2 connection, zamyka po wyjściu.

        Usage:
            with loader.connection() as conn:
                loader.upsert_rates(conn, rates)
        """
        try:
            conn = psycopg2.connect(self.dsn)
        except psycopg2.Error as e:
            raise PostgresConnectionError(
                "Postgres DB connection error") from e
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()  # close communication with the database

    def upsert_rates(
        self,
        conn,
        rates: list[ExchangeRate]
    ) -> tuple[int, int]:
        """
        Upsert list of ExchangeRate to exchange_rates_daily.

        Returns:
            (inserted_count, updated_count)
        """
        # TODO:
        # 1. Konwertuj rates -> list of tuples (currency_code, effective_date, rate_pln, table_no, datetime.now(timezone.utc))
        # 2. cursor.execute_values z UPSERT_SQL
        # 3. results = cursor.fetchall() — list of (True/False) z "inserted" column
        # 4. inserted = sum(r[0] for r in results); updated = len(results) - inserted
        # 5. log.info("rates_upserted", inserted=..., updated=..., total=len(rates))
        # 6. return inserted, updated

        current_time = datetime.now(timezone.utc)

        data_to_insert = [
            (
                rate.currency_code,
                rate.effective_date,
                rate.rate_pln,
                rate.table_no,
                current_time
            )
            for rate in rates
        ]

        if not data_to_insert:
            return 0, 0  # When the list is empty there is no reason to query the DB

        with conn.cursor() as cur:
            results = execute_values(
                cur, self.UPSERT_SQL, data_to_insert, fetch=True)
        inserted = sum([r[0] for r in results])
        updated = len(results) - inserted
        log.info("rates_upserted", inserted=inserted,
                 updated=updated, total=len(rates))
        return inserted, updated
